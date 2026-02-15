from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

if not hasattr(httpx, "BaseTransport"):
    pytest.skip("httpx/TestClient compatibility missing in current environment", allow_module_level=True)

pytest.importorskip("pgvector")

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
import app.main as main_mod
from app.models import Document, Job, User


def _build_client(tmp_path: Path) -> tuple[TestClient, sessionmaker]:
    db_path = tmp_path / "test_upload_rag.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    try:
        User.__table__.create(bind=engine, checkfirst=True)
        Document.__table__.create(bind=engine, checkfirst=True)
        Job.__table__.create(bind=engine, checkfirst=True)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"database dialect can't create required tables for this test: {exc}")

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestSessionLocal


def test_upload_job_rag_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    client, TestSessionLocal = _build_client(tmp_path)

    def fake_ingest(job_id: str, doc_id: str, file_path_str: str, filename: str, language: str):
        _ = file_path_str, filename, language
        db = TestSessionLocal()
        try:
            doc = db.get(Document, doc_id)
            job = db.get(Job, job_id)
            if doc:
                doc.status = "ready"
                doc.metadata_json = {**(doc.metadata_json or {}), "chunks": 1}
            if job:
                job.status = "completed"
                job.result = {"document_id": doc_id, "chunks": 1}
            db.commit()
        finally:
            db.close()

    monkeypatch.setattr(main_mod, "_ingest_document_job", fake_ingest)
    monkeypatch.setattr(
        main_mod,
        "_retrieve_chunks",
        lambda db, question, top_k=5, profile="balanced": [  # noqa: ARG005
            {"doc_id": "doc-1", "chunk_id": "chunk-1", "chunk_text": "wheat recommendation", "score": 0.9}
        ],
    )
    monkeypatch.setattr(
        main_mod,
        "generate_answer_with_context",
        lambda question, context_blocks, base_url, model: "Grounded answer from mocked retrieval",  # noqa: ARG005
    )

    register = client.post(
        "/v1/auth/register",
        json={"email": "upload_rag_admin@example.com", "password": "pass1234", "role": "admin", "locale": "ru"},
    )
    assert register.status_code == 200
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    upload = client.post(
        "/v1/documents",
        headers=headers,
        files={"file": ("demo.txt", b"spring wheat guidance", "text/plain")},
        data={"title": "demo", "language": "ru"},
    )
    assert upload.status_code == 200
    assert upload.json()["status"] in {"processing", "ready"}

    jobs = client.get("/v1/jobs", headers=headers)
    assert jobs.status_code == 200
    assert len(jobs.json().get("items", [])) >= 1

    rag = client.post(
        "/v1/rag/query",
        headers=headers,
        json={"question": "what to sow in spring?", "top_k": 5, "locale": "ru", "profile": "balanced"},
    )
    assert rag.status_code == 200
    assert "Grounded answer" in rag.json()["answer"]
    assert len(rag.json()["sources"]) >= 1

    app.dependency_overrides.clear()
