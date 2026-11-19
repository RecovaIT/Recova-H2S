"""Baselines, deterministic scoring, pipeline execution, real-time SSE/WS stream, and agents."""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agents.orchestrator import AGENT_DEFINITIONS, create_pipeline_run, execute_pipeline_run
from app.api.deps import AuthContext, requires
from app.core.db import SessionLocal
from app.core.errors import NotFound
from app.core.events import event_bus, format_sse
from app.core.permissions import P
from app.core.security import hash_token
from app.engine.metrics import TRACK_CONFIGS
from app.engine.scoring import ALGORITHM_VERSION
from app.models.base import utcnow
from app.models.clinical import Patient
from app.models.engine import ClinicalSynthesis, EmergencyEvent, PersonalBaseline, PipelineRun, ScoringResult
from app.models.identity import UserSession
from app.schemas.common import Page, PageParams, paginate
from app.schemas.workflow import (
    EmergencyEventOut,
    EmergencyResolveRequest,
    PipelineRunCreate,
    PipelineRunDetailOut,
    PipelineRunOut,
    ScoringResultOut,
)
from app.services import care as care_svc
from app.tasks.queue import enqueue

baselines_router = APIRouter(prefix="/baselines", tags=["baselines"])
scoring_router = APIRouter(prefix="/scoring", tags=["scoring"])
pipeline_router = APIRouter(prefix="/pipeline", tags=["pipeline"])
agents_router = APIRouter(prefix="/agents", tags=["agents"])


@baselines_router.get("/patient/{patient_id}")
def list_patient_baselines(patient_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.OBSERVATIONS_READ))):
    p = ctx.db.scalar(select(Patient).where(Patient.id == patient_id, Patient.organization_id == ctx.org_id))
    if p is None:
        raise NotFound("Patient not found")
    rows = ctx.db.scalars(
        select(PersonalBaseline)
        .where(PersonalBaseline.organization_id == ctx.org_id, PersonalBaseline.patient_id == patient_id)
        .order_by(PersonalBaseline.metric_code)
    ).all()
    return [
        {
            "id": str(b.id),
            "metric_code": b.metric_code,
            "algorithm_version": b.algorithm_version,
            "status": b.status,
            "n_windows": b.n_windows,
            "mean": b.mean,
            "sample_sd": b.sample_sd,
            "window_values": b.window_values,
            "established_at": b.established_at,
        }
        for b in rows
    ]


@baselines_router.post("/patient/{patient_id}/reset")
def reset_patient_baseline(
    patient_id: uuid.UUID,
    metric_code: str | None = Query(None),
    reason: str = Query("Clinician requested baseline reset"),
    ctx: AuthContext = Depends(requires(P.REVIEWS_SIGN)),
):
    p = ctx.db.scalar(select(Patient).where(Patient.id == patient_id, Patient.organization_id == ctx.org_id))
    if p is None:
        raise NotFound("Patient not found")
    stmt = select(PersonalBaseline).where(PersonalBaseline.organization_id == ctx.org_id, PersonalBaseline.patient_id == patient_id)
    if metric_code:
        stmt = stmt.where(PersonalBaseline.metric_code == metric_code)
    rows = ctx.db.scalars(stmt).all()
    for b in rows:
        b.status = "reset"
        b.reset_reason = reason
    ctx.audit("baseline.reset", "personal_baseline", patient_id=patient_id, details={"metric_code": metric_code, "reason": reason})
    ctx.db.commit()
    return {"reset_count": len(rows)}


@scoring_router.get("/patient/{patient_id}", response_model=list[ScoringResultOut])
def list_scoring_results(
    patient_id: uuid.UUID,
    track: str | None = Query(None),
    ctx: AuthContext = Depends(requires(P.PIPELINE_READ)),
):
    stmt = select(ScoringResult).where(ScoringResult.organization_id == ctx.org_id, ScoringResult.patient_id == patient_id)
    if track:
        ctx.require_track(track)
        stmt = stmt.where(ScoringResult.track == track)
    return list(ctx.db.scalars(stmt.order_by(ScoringResult.computed_at.desc()).limit(50)).all())


@scoring_router.get("/config")
def scoring_configuration(ctx: AuthContext = Depends(requires(P.PIPELINE_READ))):
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "tracks": {
            k: {
                "expected_streams": list(v.expected_streams),
                "min_baseline_windows": v.min_baseline_windows,
                "max_baseline_windows": v.max_baseline_windows,
                "evaluation_window_days": v.evaluation_window_days,
                "practice_gain_rate": v.practice_gain_rate,
                "metrics": [{"metric_code": m.metric_code, "weight": m.weight, "apply_practice_effect": m.apply_practice_effect, "use_reference_fallback": m.use_reference_fallback} for m in v.metrics],
            }
            for k, v in TRACK_CONFIGS.items()
        },
    }


@pipeline_router.get("/runs", response_model=Page[PipelineRunOut])
def list_pipeline_runs(
    params: PageParams = Depends(),
    patient_id: uuid.UUID | None = Query(None),
    track: str | None = Query(None),
    status: str | None = Query(None),
    risk_tier: str | None = Query(None),
    ctx: AuthContext = Depends(requires(P.PIPELINE_READ)),
):
    stmt = select(PipelineRun).where(PipelineRun.organization_id == ctx.org_id, PipelineRun.benchmark_run_id.is_(None))
    if patient_id:
        stmt = stmt.where(PipelineRun.patient_id == patient_id)
    if track:
        ctx.require_track(track)
        stmt = stmt.where(PipelineRun.track == track)
    if status:
        stmt = stmt.where(PipelineRun.status == status)
    if risk_tier:
        stmt = stmt.where(PipelineRun.risk_tier == risk_tier)
    return paginate(
        ctx.db,
        stmt,
        params,
        sortable={"created_at": PipelineRun.created_at, "risk_tier": PipelineRun.risk_tier},
        default_sort=PipelineRun.created_at.desc(),
    )


@pipeline_router.post("/runs", response_model=PipelineRunDetailOut, status_code=201)
def run_pipeline(req: PipelineRunCreate, ctx: AuthContext = Depends(requires(P.PIPELINE_RUN))):
    ctx.require_track(req.track.value)
    run = create_pipeline_run(
        ctx.db,
        organization_id=ctx.org_id,
        patient_id=req.patient_id,
        track=req.track.value,
        trigger=req.trigger,
        triggered_by_id=ctx.user.id,
        as_of=req.as_of,
        idempotency_key=req.idempotency_key,
    )
    if req.run_async:
        job = enqueue(
            ctx.db,
            "pipeline.run",
            {"run_id": str(run.id)},
            organization_id=ctx.org_id,
            idempotency_key=f"pipeline:{run.id}",
            created_by_id=ctx.user.id,
        )
        run.job_id = job.id
        ctx.db.commit()
    else:
        ctx.db.commit()
        run = execute_pipeline_run(ctx.db, run.id)

    return _build_run_detail(ctx, run.id)


@pipeline_router.get("/runs/{run_id}", response_model=PipelineRunDetailOut)
def get_pipeline_run(run_id: uuid.UUID, ctx: AuthContext = Depends(requires(P.PIPELINE_READ))):
    return _build_run_detail(ctx, run_id)


def _build_run_detail(ctx: AuthContext, run_id: uuid.UUID) -> PipelineRunDetailOut:
    run = ctx.db.scalar(
        select(PipelineRun)
        .options(selectinload(PipelineRun.steps))
        .where(PipelineRun.id == run_id, PipelineRun.organization_id == ctx.org_id)
    )
    if run is None:
        raise NotFound("Pipeline run not found")
    sr = ctx.db.scalar(select(ScoringResult).where(ScoringResult.run_id == run.id))
    syn = ctx.db.scalar(select(ClinicalSynthesis).where(ClinicalSynthesis.run_id == run.id))
    out = PipelineRunDetailOut.model_validate(run)
    # Only expose raw step payloads if caller has agents:inspect
    if not ctx.has(P.AGENTS_INSPECT):
        for st in out.steps:
            st.input_payload = None
            st.output_payload = None
    out.scoring = sr  # type: ignore[assignment]
    out.synthesis = syn  # type: ignore[assignment]
    return out


@pipeline_router.get("/events/stream")
async def sse_event_stream(ctx: AuthContext = Depends(requires(P.PIPELINE_READ))):
    """Real-time Server-Sent Events stream scoped to the caller's organisation."""
    loop = asyncio.get_running_loop()
    sub = event_bus.subscribe(f"org:{ctx.org_id}", loop)

    async def gen():
        try:
            yield format_sse({"type": "connected", "timestamp": utcnow().isoformat(), "data": {"organization_id": str(ctx.org_id)}})
            while True:
                try:
                    ev = await asyncio.wait_for(sub.queue.get(), timeout=20.0)
                    yield format_sse(ev)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            event_bus.unsubscribe(sub)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@pipeline_router.websocket("/ws")
async def ws_event_stream(websocket: WebSocket):
    """WebSocket stream authenticated via the HTTP-only session cookie."""
    from app.core.config import get_settings

    s = get_settings()
    raw_cookie = websocket.cookies.get(s.session_cookie_name)
    if not raw_cookie:
        await websocket.close(code=4401)
        return
    with SessionLocal() as db:
        sess = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(raw_cookie), UserSession.revoked_at.is_(None)))
        if sess is None or sess.expires_at <= utcnow() or sess.active_organization_id is None:
            await websocket.close(code=4401)
            return
        org_id = sess.active_organization_id

    await websocket.accept()
    loop = asyncio.get_running_loop()
    sub = event_bus.subscribe(f"org:{org_id}", loop)
    try:
        await websocket.send_text(json.dumps({"type": "connected", "organization_id": str(org_id)}))
        while True:
            try:
                ev = await asyncio.wait_for(sub.queue.get(), timeout=25.0)
                await websocket.send_text(json.dumps(ev, default=str))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe(sub)


@agents_router.get("/catalog")
def list_agents(ctx: AuthContext = Depends(requires(P.PIPELINE_READ))):
    return [
        {"agent_key": key, "agent_name": name, "step_order": order}
        for key, name, order in AGENT_DEFINITIONS
    ]


@agents_router.get("/emergencies", response_model=list[EmergencyEventOut])
def list_emergencies(status: str | None = Query(None), ctx: AuthContext = Depends(requires(P.PIPELINE_READ))):
    return care_svc.list_emergencies(ctx, status=status)


@agents_router.post("/emergencies/{event_id}/resolve", response_model=EmergencyEventOut)
def resolve_emergency(event_id: uuid.UUID, req: EmergencyResolveRequest, ctx: AuthContext = Depends(requires(P.REVIEWS_SIGN))):
    return care_svc.resolve_emergency(ctx, event_id, req)
