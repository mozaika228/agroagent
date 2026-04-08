from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

if not hasattr(httpx, "BaseTransport"):
    pytest.skip("httpx/TestClient compatibility missing in current environment", allow_module_level=True)

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import FarmField, FieldFeatureSnapshot, FieldObservation, User


def _build_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test_field_features.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    User.__table__.create(bind=engine, checkfirst=True)
    FarmField.__table__.create(bind=engine, checkfirst=True)
    FieldObservation.__table__.create(bind=engine, checkfirst=True)
    FieldFeatureSnapshot.__table__.create(bind=engine, checkfirst=True)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_field_observations_and_feature_snapshot(tmp_path: Path):
    client = _build_client(tmp_path)
    reg = client.post(
        "/v1/auth/register",
        json={"email": "field_admin@example.com", "password": "pass1234", "role": "admin", "locale": "ru"},
    )
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    field_resp = client.post(
        "/v1/fields",
        headers=headers,
        json={
            "name": "Field A",
            "region": "WKO",
            "crop": "spring wheat",
            "area_ha": 35.5,
            "soil_type": "chernozem",
            "geometry": {"type": "Polygon", "coordinates": [[[51.2, 51.3], [51.21, 51.31], [51.2, 51.3]]]},
        },
    )
    assert field_resp.status_code == 200
    field_id = field_resp.json()["field_id"]

    obs_payloads = [
        {"observed_on": "2026-03-01", "ndvi": 0.42, "soil_moisture": 41.0, "precip_7d_mm": 9.0, "temp_avg_7d_c": 6.5, "yield_t_ha": 2.4},
        {"observed_on": "2026-03-08", "ndvi": 0.39, "soil_moisture": 36.0, "precip_7d_mm": 5.0, "temp_avg_7d_c": 8.5, "yield_t_ha": 2.2},
        {"observed_on": "2026-03-15", "ndvi": 0.35, "soil_moisture": 30.0, "precip_7d_mm": 4.0, "temp_avg_7d_c": 11.0, "yield_t_ha": 2.1},
    ]
    for payload in obs_payloads:
        obs_resp = client.post(f"/v1/fields/{field_id}/observations", headers=headers, json=payload)
        assert obs_resp.status_code == 200

    features_resp = client.get(f"/v1/fields/{field_id}/features?window_size=3", headers=headers)
    assert features_resp.status_code == 200
    features = features_resp.json()
    assert features["sample_size"] == 3
    assert features["features"]["ndvi_mean"] is not None
    assert features["features"]["drought_risk_score"] is not None
    assert features["features"]["stress_label"] in {"low", "medium", "high"}

    snapshot_resp = client.post(f"/v1/fields/{field_id}/features/snapshot?window_size=3", headers=headers)
    assert snapshot_resp.status_code == 200
    snapshot = snapshot_resp.json()
    assert snapshot["field_id"] == field_id
    assert snapshot["window_size"] == 3
    assert "drought_risk_score" in snapshot["features"]

    app.dependency_overrides.clear()
