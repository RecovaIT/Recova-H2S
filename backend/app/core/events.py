"""Thread-safe + asyncio-aware + PostgreSQL LISTEN/NOTIFY cross-process event broker.

Background workers (including separate `python -m app.cli worker` processes) and
FastAPI services publish pipeline step events, emergency alerts, and referral
notifications keyed by `organization_id` (plus optional `run:<run_id>` channels).
Connected SSE/WebSocket clients receive events with zero polling, scoped strictly
to their authenticated organisation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("recova.events")
_PG_CHANNEL = "recova_events"


@dataclass
class Subscription:
    channel: str
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=lambda: asyncio.Queue(maxsize=256))


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: dict[str, list[Subscription]] = defaultdict(list)
        self._seen_ids: deque[str] = deque(maxlen=1024)
        self._seen_set: set[str] = set()
        self._listener_started = False
        self._stop_event = threading.Event()

    def _mark_seen(self, event_id: str) -> bool:
        with self._lock:
            if event_id in self._seen_set:
                return False
            if len(self._seen_ids) == self._seen_ids.maxlen:
                oldest = self._seen_ids.popleft()
                self._seen_set.discard(oldest)
            self._seen_ids.append(event_id)
            self._seen_set.add(event_id)
            return True

    def _ensure_pg_listener(self) -> None:
        from app.core.config import get_settings

        if get_settings().environment == "test":
            return
        with self._lock:
            if self._listener_started:
                return
            self._listener_started = True
            t = threading.Thread(target=self._pg_listen_loop, name="recova-pg-events", daemon=True)
            t.start()

    def _pg_listen_loop(self) -> None:
        import psycopg
        from app.core.config import get_settings

        dsn = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")
        while not self._stop_event.is_set():
            try:
                with psycopg.connect(dsn, autocommit=True) as conn:
                    conn.execute(f"LISTEN {_PG_CHANNEL}")
                    for notify in conn.notifies(timeout=5.0):
                        if self._stop_event.is_set():
                            break
                        if not notify or not notify.payload:
                            continue
                        try:
                            envelope = json.loads(notify.payload)
                            channel = envelope["channel"]
                            payload = envelope["payload"]
                            ev_id = payload.get("event_id")
                            if ev_id and not self._mark_seen(ev_id):
                                continue
                            self._deliver_local(channel, payload)
                        except Exception:  # noqa: BLE001
                            log.debug("Malformed PG event notification ignored", exc_info=True)
            except Exception:  # noqa: BLE001
                log.debug("PG LISTEN loop reconnecting", exc_info=True)
                self._stop_event.wait(2.0)

    def _pg_notify(self, channel: str, payload: dict[str, Any]) -> None:
        from app.core.config import get_settings

        if get_settings().environment == "test":
            return
        try:
            from sqlalchemy import text
            from app.core.db import engine

            serialized = json.dumps({"channel": channel, "payload": payload}, default=str)
            if len(serialized) > 7500:
                serialized = json.dumps(
                    {
                        "channel": channel,
                        "payload": {
                            "event_id": payload.get("event_id"),
                            "type": payload.get("type"),
                            "timestamp": payload.get("timestamp"),
                            "data": {"truncated": True},
                        },
                    },
                    default=str,
                )
            with engine.begin() as conn:
                conn.execute(text("SELECT pg_notify(:ch, :msg)"), {"ch": _PG_CHANNEL, "msg": serialized})
        except Exception:  # noqa: BLE001
            log.debug("PG NOTIFY skipped", exc_info=True)

    def _deliver_local(self, channel: str, payload: dict[str, Any]) -> None:
        with self._lock:
            targets = list(self._subs.get(channel, ()))
        for sub in targets:
            try:
                if sub.loop.is_closed():
                    continue
                sub.loop.call_soon_threadsafe(self._put_nonblocking, sub.queue, payload)
            except RuntimeError:
                pass

    def subscribe(self, channel: str, loop: asyncio.AbstractEventLoop) -> Subscription:
        self._ensure_pg_listener()
        sub = Subscription(channel=channel, loop=loop)
        with self._lock:
            self._subs[channel].append(sub)
        return sub

    def unsubscribe(self, sub: Subscription) -> None:
        with self._lock:
            lst = self._subs.get(sub.channel)
            if lst and sub in lst:
                lst.remove(sub)
            if lst is not None and not lst:
                self._subs.pop(sub.channel, None)

    def publish(self, channel: str, event_type: str, data: dict[str, Any]) -> None:
        event_id = str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        self._mark_seen(event_id)
        self._deliver_local(channel, payload)
        self._pg_notify(channel, payload)

    @staticmethod
    def _put_nonblocking(q: asyncio.Queue[dict[str, Any]], item: dict[str, Any]) -> None:
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            pass

    def publish_org(self, organization_id: uuid.UUID, event_type: str, data: dict[str, Any]) -> None:
        self.publish(f"org:{organization_id}", event_type, data)

    def publish_run(self, organization_id: uuid.UUID, run_id: uuid.UUID, event_type: str, data: dict[str, Any]) -> None:
        enriched = {"run_id": str(run_id), **data}
        self.publish(f"org:{organization_id}", event_type, enriched)
        self.publish(f"run:{organization_id}:{run_id}", event_type, enriched)


event_bus = EventBus()


def format_sse(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"
