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
from app.models import ChatSession, User


def _build_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test_auth_flow.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    User.__table__.create(bind=engine, checkfirst=True)
    ChatSession.__table__.create(bind=engine, checkfirst=True)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_auth_register_login_and_me_flow(tmp_path: Path):
    client = _build_client(tmp_path)

    register_resp = client.post(
        "/v1/auth/register",
        json={"email": "int_test_admin@example.com", "password": "pass1234", "role": "admin", "locale": "ru"},
    )
    assert register_resp.status_code == 200
    token = register_resp.json()["access_token"]

    login_resp = client.post(
        "/v1/auth/login",
        json={"email": "int_test_admin@example.com", "password": "pass1234"},
    )
    assert login_resp.status_code == 200
    login_token = login_resp.json()["access_token"]

    me_resp = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {login_token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "admin"

    session_resp = client.post(
        "/v1/chat/sessions",
        json={"locale": "ru"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert session_resp.status_code == 200
    assert "session_id" in session_resp.json()

    app.dependency_overrides.clear()


def test_protected_endpoint_requires_auth(tmp_path: Path):
    client = _build_client(tmp_path)
    resp = client.post("/v1/chat/sessions", json={"locale": "ru"})
    assert resp.status_code == 401
    app.dependency_overrides.clear()
