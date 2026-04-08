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
from app.models import AgentRun, AgentStep, AgentTask, SafetyAuditLog, ToolCall, ToolReliabilitySnapshot, User


def _build_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test_agent_runs.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    User.__table__.create(bind=engine, checkfirst=True)
    AgentRun.__table__.create(bind=engine, checkfirst=True)
    AgentTask.__table__.create(bind=engine, checkfirst=True)
    AgentStep.__table__.create(bind=engine, checkfirst=True)
    SafetyAuditLog.__table__.create(bind=engine, checkfirst=True)
    ToolCall.__table__.create(bind=engine, checkfirst=True)
    ToolReliabilitySnapshot.__table__.create(bind=engine, checkfirst=True)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_agent_run_endpoints(tmp_path: Path):
    client = _build_client(tmp_path)
    reg = client.post(
        "/v1/auth/register",
        json={"email": "runs_admin@example.com", "password": "pass1234", "role": "admin", "locale": "ru"},
    )
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        "/v1/agents/runs",
        headers=headers,
        json={"question": "Drought strategy for spring wheat", "locale": "ru", "rounds": 2, "include_steps": True},
    )
    assert create_resp.status_code == 200
    payload = create_resp.json()
    run_id = payload["run"]["run_id"]
    assert payload["run"]["status"] == "succeeded"
    assert len(payload["tasks"]) >= 2

    list_resp = client.get("/v1/agents/runs?limit=10", headers=headers)
    assert list_resp.status_code == 200
    assert any(item["run_id"] == run_id for item in list_resp.json())

    detail_resp = client.get(f"/v1/agents/runs/{run_id}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["run"]["run_id"] == run_id

    tasks_resp = client.get(f"/v1/agents/runs/{run_id}/tasks", headers=headers)
    assert tasks_resp.status_code == 200
    assert len(tasks_resp.json()) >= 2

    reliability_resp = client.get("/v1/agents/reliability?limit=5", headers=headers)
    assert reliability_resp.status_code == 200
    assert isinstance(reliability_resp.json(), list)

    app.dependency_overrides.clear()
