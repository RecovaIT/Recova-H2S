"""Malaffi (Abu Dhabi Health Information Exchange) integration adapter.

Important governance note:
- FHIR R4 bundle generation does NOT imply an active connection to Malaffi.
- This adapter clearly reports `not_configured` until valid Malaffi OAuth2 client
  credentials and endpoint URLs are provisioned and verified via `test_connection()`.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.models.enums import IntegrationStatus


def get_malaffi_config(org_cfg: dict[str, Any] | None = None, settings: Settings | None = None) -> dict[str, str]:
    s = settings or get_settings()
    o = org_cfg or {}
    return {
        "base_url": str(o.get("base_url") or s.malaffi_base_url or "").strip(),
        "token_url": str(o.get("token_url") or s.malaffi_token_url or "").strip(),
        "client_id": str(o.get("client_id") or s.malaffi_client_id or "").strip(),
        "client_secret": str(o.get("client_secret") or s.malaffi_client_secret or "").strip(),
    }


def is_configured(cfg: dict[str, str]) -> bool:
    return bool(cfg["base_url"] and cfg["token_url"] and cfg["client_id"] and cfg["client_secret"])


def test_connection(org_cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = get_malaffi_config(org_cfg)
    if not is_configured(cfg):
        return {
            "status": IntegrationStatus.NOT_CONFIGURED.value,
            "connected": False,
            "message": "Malaffi HIE endpoints and OAuth2 credentials are not configured. FHIR R4 export remains available offline.",
            "missing": [k for k, v in cfg.items() if not v],
        }
    try:
        tok_resp = httpx.post(
            cfg["token_url"],
            data={
                "grant_type": "client_credentials",
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
            },
            timeout=15,
        )
        tok_resp.raise_for_status()
        access_token = tok_resp.json().get("access_token")
        if not access_token:
            return {"status": IntegrationStatus.ERROR.value, "connected": False, "message": "Token endpoint did not return an access_token"}
        cap_resp = httpx.get(
            f"{cfg['base_url'].rstrip('/')}/metadata",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/fhir+json"},
            timeout=15,
        )
        cap_resp.raise_for_status()
        return {
            "status": IntegrationStatus.VERIFIED.value,
            "connected": True,
            "message": "Successfully authenticated and retrieved FHIR CapabilityStatement from Malaffi endpoint.",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": IntegrationStatus.ERROR.value,
            "connected": False,
            "message": f"Malaffi connection failed: {type(exc).__name__}: {exc}",
        }


def push_fhir_bundle(bundle: dict[str, Any], org_cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = get_malaffi_config(org_cfg)
    if not is_configured(cfg):
        return {
            "status": IntegrationStatus.NOT_CONFIGURED.value,
            "submitted": False,
            "message": "Malaffi credentials are not configured; download the FHIR R4 bundle for manual exchange.",
        }
    try:
        tok = httpx.post(
            cfg["token_url"],
            data={"grant_type": "client_credentials", "client_id": cfg["client_id"], "client_secret": cfg["client_secret"]},
            timeout=15,
        )
        tok.raise_for_status()
        access_token = tok.json()["access_token"]
        res = httpx.post(
            cfg["base_url"].rstrip("/"),
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/fhir+json"},
            json=bundle,
            timeout=25,
        )
        res.raise_for_status()
        return {"status": "submitted", "submitted": True, "response_status": res.status_code, "response": res.json()}
    except Exception as exc:  # noqa: BLE001
        return {"status": IntegrationStatus.ERROR.value, "submitted": False, "message": f"{type(exc).__name__}: {exc}"}
