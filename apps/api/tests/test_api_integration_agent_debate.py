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
from app.models import AgentStep, User


def _build_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test_agent_debate.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    User.__table__.create(bind=engine, checkfirst=True)
    AgentStep.__table__.create(bind=engine, checkfirst=True)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_agent_debate_returns_verifiable_chain(tmp_path: Path):
    client = _build_client(tmp_path)

    reg = client.post(
        "/v1/auth/register",
        json={"email": "debate_admin@example.com", "password": "pass1234", "role": "admin", "locale": "ru"},
    )
    assert reg.status_code == 200
    token = reg.json()["access_token"]

    resp = client.post(
        "/v1/agents/debate",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "Drought strategy for spring wheat", "locale": "ru", "include_steps": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["winner"] in {"A", "B"}
    assert len(data["steps"]) >= 5
    assert data["steps"][0]["parent_hash"] is None
    for i in range(1, len(data["steps"])):
        assert data["steps"][i]["parent_hash"] == data["steps"][i - 1]["step_hash"]

    trace_id = data["trace_id"]
    trace_resp = client.get(f"/v1/agents/traces/{trace_id}", headers={"Authorization": f"Bearer {token}"})
    assert trace_resp.status_code == 200
    trace_data = trace_resp.json()
    assert trace_data["trace_id"] == trace_id
    assert len(trace_data["steps"]) == len(data["steps"])

    metrics_resp = client.get("/v1/agents/metrics", headers={"Authorization": f"Bearer {token}"})
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert metrics["total_runs"] >= 1
    assert metrics["last_trace_id"] == trace_id
    assert metrics["winner_a"] + metrics["winner_b"] >= 1
    assert isinstance(metrics["avg_latency_ms"], float)

    app.dependency_overrides.clear()
