"""Tests for live backend i18n catalog & safe dynamic translation API."""

from fastapi.testclient import TestClient


def test_i18n_catalog_returns_runtime_arabic_entries(client: TestClient):
    res = client.get("/api/v1/i18n/catalog", params={"lang": "ar"})
    assert res.status_code == 200
    body = res.json()
    assert body["lang"] == "ar"
    assert body["catalog"]["EMERGENCY_BYPASS"]
    assert body["catalog"]["pending_clinician_review"]
    assert body["catalog"]["Your Recova care plan was updated"]


def test_i18n_translate_batch_handles_patterns_and_protects_clinical_ids(client: TestClient):
    res = client.post(
        "/api/v1/i18n/translate",
        json={
            "target_lang": "ar",
            "texts": [
                "Overdue by 2d 4h",
                "Risk Tier: AMBER",
                "MRN-10042",
                "clinician@hospital.ae",
                "Consent granted: data_processing",
            ],
        },
    )
    assert res.status_code == 200
    translations = res.json()["translations"]
    assert translations["Overdue by 2d 4h"].startswith("متأخر بمقدار")
    assert translations["Risk Tier: AMBER"].startswith("مستوى الخطر:")
    assert translations["Consent granted: data_processing"].startswith("تم منح الموافقة:")
    # Clinical IDs and emails must never be mutated
    assert "MRN-10042" not in translations
    assert "clinician@hospital.ae" not in translations
