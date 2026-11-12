"""Pytest fixtures backed by real PostgreSQL (`recova_test` database)."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "postgresql+psycopg://recova:recova@127.0.0.1:55432/recova_test"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-00000000000000"
os.environ["COOKIE_SECURE"] = "false"
os.environ["RUN_EMBEDDED_WORKER"] = "false"
os.environ["LLM_PROVIDER"] = "none"

from app.core.config import get_settings

get_settings.cache_clear()

from app.core.db import SessionLocal, engine
from app.core.rate_limit import limiter
from app.main import create_app
from app.models import Base


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables() -> Generator[None, None, None]:
    limiter.reset()
    with engine.begin() as conn:
        tables = [t.name for t in reversed(Base.metadata.sorted_tables)]
        if tables:
            conn.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    app = create_app()
    with TestClient(app) as c:
        yield c


def auth_headers(c: TestClient) -> dict[str, str]:
    csrf = c.cookies.get("recova_csrf")
    return {"X-CSRF-Token": csrf} if csrf else {}


def bootstrap_org_and_admin(
    c: TestClient,
    *,
    org_name: str = "Abu Dhabi Wellness Center",
    slug: str = "ad-wellness",
    email: str = "admin@adwellness.ae",
    password: str = "SecurePass123!",
) -> dict:
    r = c.post(
        "/api/v1/auth/bootstrap",
        json={
            "organization_name": org_name,
            "organization_slug": slug,
            "org_type": "hospital",
            "enabled_tracks": ["core", "loop", "neuro", "worksafe"],
            "admin_email": email,
            "admin_full_name": "Dr. Layla Al-Hashimi",
            "admin_password": password,
            "admin_license_number": "DOH-PHY-1001",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()
