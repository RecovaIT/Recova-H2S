"""Persistent DB-backed job queue with retries, timeouts, idempotency and history.

- `enqueue()` inserts a Job row (idempotent on `idempotency_key`).
- `Worker` threads claim jobs with `SELECT ... FOR UPDATE SKIP LOCKED`, so several
  worker processes can run safely against the same database.
- Handlers are registered with `@register("job_type")` and receive `(db, job)`.
- Periodic jobs (SLA monitor etc.) are registered with `@periodic(name, seconds)`
  and enqueued by the scheduler thread with a time-bucketed idempotency key.
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models.base import utcnow
from app.models.enums import JobStatus
from app.models.ops import Job

log = logging.getLogger("recova.jobs")

Handler = Callable[[Session, Job], dict | None]
_HANDLERS: dict[str, Handler] = {}


@dataclass
class _Periodic:
    name: str
    job_type: str
    every_seconds: int
    payload: dict


_PERIODIC: list[_Periodic] = []


def register(job_type: str) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _HANDLERS[job_type] = fn
        return fn

    return deco


def periodic(job_type: str, every_seconds: int, payload: dict | None = None) -> None:
    _PERIODIC.append(_Periodic(job_type, job_type, every_seconds, payload or {}))


def registered_job_types() -> list[str]:
    return sorted(_HANDLERS)


def enqueue(
    db: Session,
    job_type: str,
    payload: dict[str, Any],
    *,
    organization_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    max_attempts: int = 3,
    timeout_seconds: int = 120,
    run_after: datetime | None = None,
    created_by_id: uuid.UUID | None = None,
) -> Job:
    """Insert a job in the caller's transaction. Returns the existing job if the key exists."""
    if idempotency_key:
        existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
        if existing is not None:
            return existing
    job = Job(
        organization_id=organization_id,
        job_type=job_type,
        status=JobStatus.QUEUED,
        payload=payload,
        idempotency_key=idempotency_key,
        max_attempts=max_attempts,
        timeout_seconds=timeout_seconds,
        run_after=run_after or utcnow(),
        created_by_id=created_by_id,
        history=[],
    )
    db.add(job)
    db.flush()
    return job


def _claim(db: Session, worker_id: str) -> Job | None:
    now = utcnow()
    stmt = (
        select(Job)
        .where(
            or_(Job.status == JobStatus.QUEUED, Job.status == JobStatus.FAILED),
            Job.run_after <= now,
            Job.attempts < Job.max_attempts,
        )
        .order_by(Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = db.scalar(stmt)
    if job is None:
        return None
    job.status = JobStatus.RUNNING
    job.locked_at = now
    job.locked_by = worker_id
    job.started_at = now
    job.attempts += 1
    db.commit()
    return job


def _recover_stale(db: Session) -> None:
    """Jobs stuck in RUNNING beyond their timeout (crashed worker) become retryable."""
    rows = db.scalars(select(Job).where(Job.status == JobStatus.RUNNING)).all()
    now = utcnow()
    for j in rows:
        if j.locked_at and j.locked_at + timedelta(seconds=j.timeout_seconds * 2) < now:
            j.status = JobStatus.FAILED if j.attempts < j.max_attempts else JobStatus.DEAD
            j.last_error = "Worker lost or job exceeded timeout (recovered)"
            j.history = [*j.history, {"attempt": j.attempts, "status": j.status, "error": j.last_error, "at": now.isoformat()}]
    db.commit()


_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="recova-job")


def execute_job(job_id: uuid.UUID) -> None:
    """Run one claimed job with timeout + retry bookkeeping (separate session)."""
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        handler = _HANDLERS.get(job.job_type)
        started = utcnow()
        if handler is None:
            job.status = JobStatus.DEAD
            job.last_error = f"No handler registered for job type '{job.job_type}'"
            job.finished_at = started
            db.commit()
            return

        def _run() -> dict | None:
            with SessionLocal() as inner:
                j = inner.get(Job, job_id)
                assert j is not None
                try:
                    res = handler(inner, j)
                    inner.commit()
                    return res
                except Exception:
                    inner.rollback()
                    raise

        status: str
        error: str | None = None
        result: dict | None = None
        try:
            result = _executor.submit(_run).result(timeout=job.timeout_seconds)
            status = JobStatus.SUCCEEDED
        except FutureTimeout:
            error = f"Timed out after {job.timeout_seconds}s"
            status = JobStatus.FAILED
        except Exception as exc:  # noqa: BLE001
            error = f"{type(exc).__name__}: {exc}"
            log.error("Job %s (%s) failed: %s\n%s", job.id, job.job_type, error, traceback.format_exc())
            status = JobStatus.FAILED

        db.refresh(job)
        finished = utcnow()
        if status == JobStatus.FAILED and job.attempts >= job.max_attempts:
            status = JobStatus.DEAD
        job.status = status
        job.result = result if status == JobStatus.SUCCEEDED else job.result
        job.last_error = error
        job.finished_at = finished
        job.locked_at = None
        job.locked_by = None
        if status == JobStatus.FAILED:
            # exponential backoff: 5s, 20s, 80s ...
            job.run_after = finished + timedelta(seconds=5 * (4 ** (job.attempts - 1)))
        job.history = [
            *job.history,
            {
                "attempt": job.attempts,
                "status": status,
                "started": started.isoformat(),
                "finished": finished.isoformat(),
                "error": error,
            },
        ]
        db.commit()
        if status == JobStatus.DEAD:
            _on_dead(job.id)


_DEAD_HOOKS: list[Callable[[uuid.UUID], None]] = []


def on_dead(fn: Callable[[uuid.UUID], None]) -> Callable[[uuid.UUID], None]:
    _DEAD_HOOKS.append(fn)
    return fn


def _on_dead(job_id: uuid.UUID) -> None:
    for fn in _DEAD_HOOKS:
        try:
            fn(job_id)
        except Exception:  # noqa: BLE001
            log.exception("dead-job hook failed")


def run_pending_jobs(max_jobs: int = 100) -> int:
    """Synchronously drain the queue (used by tests and CLI)."""
    worker_id = f"inline-{os.getpid()}"
    n = 0
    while n < max_jobs:
        with SessionLocal() as db:
            job = _claim(db, worker_id)
            if job is None:
                break
            jid = job.id
        execute_job(jid)
        n += 1
    return n


class Worker:
    def __init__(self, concurrency: int = 2) -> None:
        self.worker_id = f"{socket.gethostname()}-{os.getpid()}"
        self.concurrency = concurrency
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        for i in range(self.concurrency):
            t = threading.Thread(target=self._loop, name=f"recova-worker-{i}", daemon=True)
            t.start()
            self._threads.append(t)
        t = threading.Thread(target=self._scheduler, name="recova-scheduler", daemon=True)
        t.start()
        self._threads.append(t)
        log.info("Job worker started (%s, concurrency=%s)", self.worker_id, self.concurrency)

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        interval = get_settings().worker_poll_interval_seconds
        while not self._stop.is_set():
            try:
                with SessionLocal() as db:
                    job = _claim(db, self.worker_id)
                    jid = job.id if job else None
                if jid is None:
                    self._stop.wait(interval)
                    continue
                execute_job(jid)
            except Exception:  # noqa: BLE001
                log.exception("Worker loop error")
                self._stop.wait(interval * 5)

    def _scheduler(self) -> None:
        while not self._stop.is_set():
            try:
                enqueue_periodic_jobs()
                with SessionLocal() as db:
                    _recover_stale(db)
            except Exception:  # noqa: BLE001
                log.exception("Scheduler error")
            self._stop.wait(get_settings().scheduler_interval_seconds)


def enqueue_periodic_jobs(now: datetime | None = None) -> int:
    now = now or utcnow()
    created = 0
    for p in _PERIODIC:
        bucket = int(now.timestamp()) // p.every_seconds
        key = f"periodic:{p.job_type}:{bucket}"
        with SessionLocal() as db:
            try:
                before = db.scalar(select(Job.id).where(Job.idempotency_key == key))
                if before is None:
                    enqueue(db, p.job_type, dict(p.payload), idempotency_key=key, max_attempts=2, timeout_seconds=300)
                    db.commit()
                    created += 1
            except IntegrityError:
                db.rollback()
    return created


def cancel_job(db: Session, job_id: uuid.UUID) -> None:
    db.execute(update(Job).where(Job.id == job_id, Job.status == JobStatus.QUEUED).values(status=JobStatus.DEAD, last_error="Cancelled"))
