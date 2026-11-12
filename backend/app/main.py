"""FastAPI application entrypoint for the Recova Anticipatory Health Platform."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

import app.tasks.handlers  # noqa: F401 - register job handlers & periodic tasks
from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.errors import install_exception_handlers
from app.core.rate_limit import limiter
from app.tasks.queue import Worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
log = logging.getLogger("recova")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    s = get_settings()
    worker: Worker | None = None
    if s.run_embedded_worker and s.environment != "test":
        worker = Worker(concurrency=2)
        worker.start()
    try:
        yield
    finally:
        if worker is not None:
            worker.stop()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=s.app_name,
        version="2.0.0",
        docs_url="/docs" if s.environment != "production" else None,
        redoc_url="/redoc" if s.environment != "production" else None,
        openapi_url="/openapi.json" if s.environment != "production" else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )

    @app.middleware("http")
    async def security_and_context_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = req_id

        if s.environment != "test" and request.url.path.startswith(s.api_prefix):
            ip = request.client.host if request.client else "unknown"
            limiter.check(f"api:{ip}", s.rate_limit_default_per_minute, 60.0)

        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), geolocation=()"
        if s.cookie_secure:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    install_exception_handlers(app)
    app.include_router(api_v1_router, prefix=s.api_prefix)

    @app.get("/healthz", tags=["system"])
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz", tags=["system"])
    def readyz():
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}

    return app


app = create_app()
