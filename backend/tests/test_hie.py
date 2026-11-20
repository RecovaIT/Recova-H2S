from datetime import timedelta
import uuid

from app.core.db import SessionLocal
from app.models.base import utcnow
from app.models.clinical import Consent
from tests.conftest import auth_headers, bootstrap_org_and_admin

def test_hie_export_and_push_require_latest_effective_grant(client):
    bootstrap_org_and_admin(client)
    h = auth_headers(client)
    patient = client.post('/api/v1/patients', headers=h, json={'mrn':'HIE-1','given_name':'Test','family_name':'Consent','tracks':['core']}).json()
    pid = patient['id']
    def blocked():
        assert client.get(f'/api/v1/fhir/patients/{pid}/bundle').status_code == 403
        assert client.post(f'/api/v1/fhir/patients/{pid}/push-malaffi', headers=h).status_code == 403
    def record(status, offset, expiry=None):
        with SessionLocal() as db:
            from app.models.clinical import Patient
            p = db.get(Patient, uuid.UUID(pid))
            db.add(Consent(organization_id=p.organization_id, patient_id=p.id, scope='hie_sharing', status=status, effective_at=utcnow()+timedelta(minutes=offset), expires_at=expiry))
            db.commit()
    blocked()
    record('granted', 10)
    blocked()
    record('granted', -10, utcnow()-timedelta(minutes=1))
    blocked()
    record('granted', -8)
    assert client.get(f'/api/v1/fhir/patients/{pid}/bundle').status_code == 200
    record('revoked', -6)
    blocked()
    record('granted', -4)
    assert client.get(f'/api/v1/fhir/patients/{pid}/bundle').status_code == 200
