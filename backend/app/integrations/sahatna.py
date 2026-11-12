"""Sahatna (Abu Dhabi patient-facing super-app) integration adapter.

Reports `not_configured` until Sahatna API base URL and API key are configured
and verified; never simulates external delivery.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.models.enums import IntegrationStatus, NotificationStatus


def get_sahatna_config(org_cfg: dict[str, Any] | None = None, settings: Settings | None = None) -> dict[str, str]:
    s = settings or get_settings()
    o = org_cfg or {}
    return {
        "base_url": str(o.get("base_url") or s.sahatna_base_url or "").strip(),
        "api_key": str(o.get("api_key") or s.sahatna_api_key or "").strip(),
    }


def is_configured(cfg: dict[str, str]) -> bool:
    return bool(cfg["base_url"] and cfg["api_key"])


def test_connection(org_cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = get_sahatna_config(org_cfg)
    if not is_configured(cfg):
        return {
            "status": IntegrationStatus.NOT_CONFIGURED.value,
            "connected": False,
            "message": "Sahatna API base URL and key are not configured.",
            "missing": [k for k, v in cfg.items() if not v],
        }
    try:
        r = httpx.get(
            f"{cfg['base_url'].rstrip('/')}/health",
            headers={"Authorization": f"Bearer {cfg['api_key']}"},
            timeout=15,
        )
        r.raise_for_status()
        return {"status": IntegrationStatus.VERIFIED.value, "connected": True, "message": "Sahatna endpoint reachable."}
    except Exception as exc:  # noqa: BLE001
        return {"status": IntegrationStatus.ERROR.value, "connected": False, "message": f"{type(exc).__name__}: {exc}"}


def send_sahatna_nudge(
    *,
    patient_id: uuid.UUID | None,
    subject: str,
    body: str,
    sahatna_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = get_sahatna_config(sahatna_cfg)
    if not is_configured(cfg):
        return {
            "status": NotificationStatus.NOT_CONFIGURED.value,
            "error": "Sahatna integration is not configured (requires SAHATNA_BASE_URL and SAHATNA_API_KEY).",
        }
    if patient_id is None:
        return {"status": NotificationStatus.FAILED.value, "error": "Patient identifier required for Sahatna nudge."}
    try:
        r = httpx.post(
            f"{cfg['base_url'].rstrip('/')}/v1/nudges",
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json={"patient_ref": f"SAH-{patient_id}", "title": subject, "message": body},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return {"status": NotificationStatus.SENT.value, "provider_message_id": data.get("message_id")}
    except Exception as exc:  # noqa: BLE001
        return {"status": NotificationStatus.FAILED.value, "error": f"{type(exc).__name__}: {exc}"}
