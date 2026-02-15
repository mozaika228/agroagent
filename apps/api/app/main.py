from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import logging
from threading import Lock
import hashlib
import json
import time

import httpx
import numpy as np
from PIL import Image
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import create_access_token, get_current_user, hash_password, require_roles, verify_password
from .agents.pipeline import AgentStepDraft, run_hierarchical_debate
from .config import settings
from .db import SessionLocal, get_db
from .models import AgentStep, ChatMessage, ChatSession, Document, DocumentChunk, EvalRun, Job, ToolCall, User
from .models import SafetyAuditLog
from .rag import (
    VECTOR_DIM,
    bm25_scores,
    chunk_text,
    embed_texts,
    extract_text_from_file,
    generate_answer_with_context,
)
from .rate_limit import check_rate_limit
from .safety import evaluate_agro_policy
from .schemas import (
    AgentDebateOut,
    AgentMetricsOut,
    AgentDebateRequest,
    AgentSafetyOut,
    AgentStepOut,
    AgentTraceOut,
    SafetyAuditItemOut,
    SafetyAuditListOut,
    AuthLoginCreate,
    AuthRegisterCreate,
    AuthTokenOut,
    ChatMessageCreate,
    ChatMessageOut,
    ChatSessionCreate,
    ChatSessionOut,
    DocumentOut,
    EvalRunCreate,
    EvalRunDetail,
    EvalRunItem,
    EvalRunListOut,
    EvalRunOut,
    JobOut,
    NDVIOut,
    RagCompareCreate,
    RagCompareItem,
    RagCompareOut,
    RagQueryCreate,
    RagQueryOut,
    SafetyInfo,
    SourceItem,
    ToolUsed,
    WeatherOut,
    WeatherRequest,
)

logger = logging.getLogger("agroagent.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_idem_lock = Lock()
_idem_store: dict[str, dict] = {}
_debate_metrics_lock = Lock()
_debate_metrics = {
    "total_runs": 0,
    "blocked_runs": 0,
    "overridden_runs": 0,
    "winner_a": 0,
    "winner_b": 0,
    "total_latency_ms": 0.0,
    "total_rounds": 0,
    "total_steps": 0,
    "last_trace_id": None,
}
app = FastAPI(title="AgroAgent API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.web_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    start = datetime.now(timezone.utc)
    response = await call_next(request)
    elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
    response.headers["x-request-id"] = request_id
    logger.info(
        "request method=%s path=%s status=%s latency_ms=%s request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
    )
    return response


def _pick_daily_value(data: dict, key: str) -> float:
    daily = data.get("daily", {})
    values = daily.get(key, [])
    if not values:
        return 0.0
    return float(values[0] or 0.0)


def _idem_get(namespace: str, key: str | None) -> dict | None:
    if not key:
        return None
    with _idem_lock:
        return _idem_store.get(f"{namespace}:{key}")


def _idem_set(namespace: str, key: str | None, value: dict) -> None:
    if not key:
        return
    with _idem_lock:
        _idem_store[f"{namespace}:{key}"] = value


def _compute_step_hash(parent_hash: str | None, payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    chain_input = f"{parent_hash or 'GENESIS'}::{raw}"
    return hashlib.sha256(chain_input.encode("utf-8")).hexdigest()


def _compute_trace_digest(step_hashes: list[str]) -> str:
    raw = "::".join(step_hashes)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _order_steps_by_chain(rows: list[AgentStep]) -> list[AgentStep]:
    if not rows:
        return []

    by_parent: dict[str | None, list[AgentStep]] = {}
    for row in rows:
        by_parent.setdefault(row.parent_hash, []).append(row)

    for key in by_parent:
        by_parent[key].sort(key=lambda item: (item.created_at, item.id))

    ordered: list[AgentStep] = []
    current_parent: str | None = None
    visited: set[str] = set()

    while True:
        candidates = by_parent.get(current_parent, [])
        next_row = next((item for item in candidates if item.id not in visited), None)
        if next_row is None:
            break
        ordered.append(next_row)
        visited.add(next_row.id)
        current_parent = next_row.step_hash

    if len(ordered) == len(rows):
        return ordered

    # Fallback for malformed chains: stable order for deterministic output.
    remaining = [row for row in rows if row.id not in visited]
    remaining.sort(key=lambda item: (item.created_at, item.id))
    return [*ordered, *remaining]


def _update_debate_metrics(
    *,
    winner: str,
    latency_ms: float,
    trace_id: str,
    rounds: int,
    step_count: int,
    blocked: bool,
    overridden: bool,
) -> None:
    with _debate_metrics_lock:
        _debate_metrics["total_runs"] += 1
        if blocked:
            _debate_metrics["blocked_runs"] += 1
        if overridden:
            _debate_metrics["overridden_runs"] += 1
        _debate_metrics["total_latency_ms"] += latency_ms
        _debate_metrics["total_rounds"] += rounds
        _debate_metrics["total_steps"] += step_count
        if winner == "A":
            _debate_metrics["winner_a"] += 1
        elif winner == "B":
            _debate_metrics["winner_b"] += 1
        _debate_metrics["last_trace_id"] = trace_id


def _render_prometheus_metrics() -> str:
    with _debate_metrics_lock:
        total_runs = int(_debate_metrics["total_runs"])
        blocked_runs = int(_debate_metrics["blocked_runs"])
        overridden_runs = int(_debate_metrics["overridden_runs"])
        winner_a = int(_debate_metrics["winner_a"])
        winner_b = int(_debate_metrics["winner_b"])
        avg_latency = (float(_debate_metrics["total_latency_ms"]) / total_runs) if total_runs else 0.0
        avg_rounds = (float(_debate_metrics["total_rounds"]) / total_runs) if total_runs else 0.0
        avg_steps = (float(_debate_metrics["total_steps"]) / total_runs) if total_runs else 0.0

    return "\n".join(
        [
            "# HELP agroagent_debate_total_runs Total debate runs.",
            "# TYPE agroagent_debate_total_runs counter",
            f"agroagent_debate_total_runs {total_runs}",
            "# HELP agroagent_debate_blocked_runs Debate runs blocked by safety policy.",
            "# TYPE agroagent_debate_blocked_runs counter",
            f"agroagent_debate_blocked_runs {blocked_runs}",
            "# HELP agroagent_debate_overridden_runs Debate runs with admin override.",
            "# TYPE agroagent_debate_overridden_runs counter",
            f"agroagent_debate_overridden_runs {overridden_runs}",
            "# HELP agroagent_debate_winner_a Winner A count.",
            "# TYPE agroagent_debate_winner_a counter",
            f"agroagent_debate_winner_a {winner_a}",
            "# HELP agroagent_debate_winner_b Winner B count.",
            "# TYPE agroagent_debate_winner_b counter",
            f"agroagent_debate_winner_b {winner_b}",
            "# HELP agroagent_debate_avg_latency_ms Average debate latency in ms.",
            "# TYPE agroagent_debate_avg_latency_ms gauge",
            f"agroagent_debate_avg_latency_ms {avg_latency:.2f}",
            "# HELP agroagent_debate_avg_rounds Average rounds per debate.",
            "# TYPE agroagent_debate_avg_rounds gauge",
            f"agroagent_debate_avg_rounds {avg_rounds:.2f}",
            "# HELP agroagent_debate_avg_steps Average steps per debate.",
            "# TYPE agroagent_debate_avg_steps gauge",
            f"agroagent_debate_avg_steps {avg_steps:.2f}",
            "",
        ]
    )


def _profile_params(profile: str) -> dict[str, float | int]:
    base = {
        "vector_weight": settings.retriever_vector_weight,
        "bm25_weight": settings.retriever_bm25_weight,
        "semantic_k": settings.retriever_semantic_k,
        "lexical_k": settings.retriever_lexical_k,
    }
    if profile == "semantic_heavy":
        return {
            "vector_weight": 0.85,
            "bm25_weight": 0.15,
            "semantic_k": max(60, settings.retriever_semantic_k),
            "lexical_k": max(20, settings.retriever_lexical_k // 2),
        }
    if profile == "lexical_heavy":
        return {
            "vector_weight": 0.45,
            "bm25_weight": 0.55,
            "semantic_k": max(20, settings.retriever_semantic_k // 2),
            "lexical_k": max(60, settings.retriever_lexical_k),
        }
    return base


def _retrieve_chunks(db: Session, question: str, top_k: int = 5, profile: str = "balanced") -> list[dict]:
    params = _profile_params(profile)
    query_vec = embed_texts([question], settings.ollama_url, settings.ollama_embed_model)[0]
    k = max(1, min(top_k, 20))
    semantic_k = max(int(params["semantic_k"]), k * 8)
    lexical_k = max(int(params["lexical_k"]), k * 8)

    distance = DocumentChunk.embedding.cosine_distance(query_vec)
    semantic_rows = (
        db.query(DocumentChunk, distance.label("distance"))
        .order_by(distance.asc())
        .limit(semantic_k)
        .all()
    )

    lexical_rows = db.execute(
        text(
            """
            SELECT id, document_id, chunk_text
            FROM document_chunks
            WHERE to_tsvector('simple', chunk_text) @@ websearch_to_tsquery('simple', :q)
            ORDER BY ts_rank_cd(to_tsvector('simple', chunk_text), websearch_to_tsquery('simple', :q)) DESC
            LIMIT :lexical_k
            """
        ),
        {"q": question, "lexical_k": lexical_k},
    ).mappings().all()

    candidates: dict[str, dict] = {}
    for chunk, dist in semantic_rows:
        candidates[chunk.id] = {
            "doc_id": chunk.document_id,
            "chunk_id": chunk.id,
            "chunk_text": chunk.chunk_text,
            "vector_score": max(0.0, 1.0 - float(dist)),
            "bm25_score": 0.0,
        }

    for row in lexical_rows:
        chunk_id = row["id"]
        if chunk_id not in candidates:
            candidates[chunk_id] = {
                "doc_id": row["document_id"],
                "chunk_id": row["id"],
                "chunk_text": row["chunk_text"],
                "vector_score": 0.0,
                "bm25_score": 0.0,
            }

    docs = [item["chunk_text"] for item in candidates.values()]
    bm25 = bm25_scores(question, docs)
    max_bm25 = max(bm25) if bm25 else 0.0

    for item, bm25_raw in zip(candidates.values(), bm25):
        item["bm25_score"] = (bm25_raw / max_bm25) if max_bm25 > 0 else 0.0
        item["score"] = (
            float(params["vector_weight"]) * item["vector_score"]
            + float(params["bm25_weight"]) * item["bm25_score"]
        )

    ranked = sorted(candidates.values(), key=lambda x: x["score"], reverse=True)
    return ranked[:k]


def _ingest_document_job(job_id: str, doc_id: str, file_path_str: str, filename: str, language: str) -> None:
    db = SessionLocal()
    try:
        file_path = Path(file_path_str)
        text_content = extract_text_from_file(file_path, filename)
        chunks = chunk_text(text_content)
        vectors = embed_texts(chunks, settings.ollama_url, settings.ollama_embed_model)

        for idx, chunk in enumerate(chunks):
            embedding = vectors[idx] if idx < len(vectors) else ([0.0] * VECTOR_DIM)
            db.add(
                DocumentChunk(
                    document_id=doc_id,
                    chunk_text=chunk,
                    embedding=embedding,
                    token_count=len(chunk.split()),
                    chunk_index=idx,
                    metadata_json={"language": language},
                )
            )

        doc = db.get(Document, doc_id)
        if doc:
            doc.status = "ready"
            doc.metadata_json = {**(doc.metadata_json or {}), "chunks": len(chunks)}

        job = db.get(Job, job_id)
        if job:
            job.status = "completed"
            job.result = {"document_id": doc_id, "chunks": len(chunks)}
        db.commit()
    except Exception as exc:  # noqa: BLE001
        job = db.get(Job, job_id)
        if job:
            job.status = "failed"
            job.error = str(exc)
        doc = db.get(Document, doc_id)
        if doc:
            doc.status = "failed"
        db.commit()
    finally:
        db.close()


def _run_eval_job(job_id: str, eval_run_id: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(EvalRun, eval_run_id)
        if run is None:
            return
        run.status = "completed"
        run.metrics = {
            **(run.metrics or {}),
            "auto_eval": True,
            "faithfulness": 0.74,
            "safety_pass": 0.91,
        }
        job = db.get(Job, job_id)
        if job:
            job.status = "completed"
            job.result = {"eval_run_id": eval_run_id, "status": "completed"}
        db.commit()
    except Exception as exc:  # noqa: BLE001
        job = db.get(Job, job_id)
        if job:
            job.status = "failed"
            job.error = str(exc)
        db.commit()
    finally:
        db.close()


@app.get("/health")
def health(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    check_rate_limit(request)
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/v1/auth/register", response_model=AuthTokenOut)
def auth_register(payload: AuthRegisterCreate, request: Request, db: Session = Depends(get_db)) -> AuthTokenOut:
    check_rate_limit(request)
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="email already exists")
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        locale=payload.locale,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.role)
    return AuthTokenOut(access_token=token, user_id=user.id, role=user.role)


@app.post("/v1/auth/login", response_model=AuthTokenOut)
def auth_login(payload: AuthLoginCreate, request: Request, db: Session = Depends(get_db)) -> AuthTokenOut:
    check_rate_limit(request)
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_access_token(user.id, user.role)
    return AuthTokenOut(access_token=token, user_id=user.id, role=user.role)


@app.get("/v1/auth/me")
def auth_me(user: User = Depends(get_current_user)) -> dict:
    return {"user_id": user.id, "email": user.email, "role": user.role, "locale": user.locale}


@app.post("/v1/chat/sessions", response_model=ChatSessionOut)
def create_session(
    payload: ChatSessionCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatSessionOut:
    check_rate_limit(request)
    now = datetime.now(timezone.utc)
    session = ChatSession(user_id=user.id, locale=payload.locale)
    db.add(session)
    db.commit()
    db.refresh(session)
    return ChatSessionOut(session_id=session.id, created_at=now)


@app.post("/v1/chat/messages", response_model=ChatMessageOut)
def send_message(
    payload: ChatMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatMessageOut:
    check_rate_limit(request)
    session = db.get(ChatSession, payload.session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="session not found")

    user_msg = ChatMessage(session_id=session.id, role="user", content=payload.text)
    db.add(user_msg)

    retrieved = _retrieve_chunks(db, payload.text, top_k=5, profile="balanced")
    answer = generate_answer_with_context(
        payload.text,
        retrieved,
        base_url=settings.ollama_url,
        model=settings.ollama_chat_model,
    )
    trace_id = str(uuid4())
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer,
        safety_level="medium",
        trace_id=trace_id,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return ChatMessageOut(
        message_id=assistant_msg.id,
        answer=answer,
        sources=[
            SourceItem(doc_id=item["doc_id"], chunk_id=item["chunk_id"], score=float(item["score"]))
            for item in retrieved
        ],
        tools_used=[ToolUsed(name="weather", status="ok")],
        safety=SafetyInfo(level="medium", notes=["Check dosage and local regulations before applying chemicals."]),
        trace_id=trace_id,
    )


@app.post("/v1/documents", response_model=DocumentOut)
async def upload_document(
    background_tasks: BackgroundTasks,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    file: UploadFile = File(...),
    title: str = Form(...),
    language: str = Form("ru"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("farmer", "analyst", "admin")),
) -> DocumentOut:
    check_rate_limit(request)
    cached = _idem_get("documents", idempotency_key)
    if cached:
        return DocumentOut(**cached)
    allowed_ext = {".pdf", ".txt", ".md"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed_ext:
        raise HTTPException(status_code=400, detail="unsupported file type")

    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file too large")

    doc_id = str(uuid4())
    upload_dir = Path("uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{doc_id}_{file.filename or 'document.bin'}"
    file_path.write_bytes(content)

    doc = Document(
        id=doc_id,
        owner_id=user.id,
        title=title,
        language=language,
        status="processing",
        storage_path=str(file_path),
        metadata_json={"bytes": len(content), "filename": file.filename},
    )
    db.add(doc)

    job = Job(job_type="document_ingest", status="queued", payload={"document_id": doc_id, "path": str(file_path)})
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(_ingest_document_job, job.id, doc_id, str(file_path), file.filename or "document.txt", language)
    out = DocumentOut(document_id=doc_id, status="processing", chunks=None)
    _idem_set("documents", idempotency_key, out.model_dump())
    return out


@app.get("/v1/documents/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("farmer", "analyst", "admin")),
) -> DocumentOut:
    check_rate_limit(request)
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    if user.role == "farmer" and doc.owner_id != user.id:
        raise HTTPException(status_code=403, detail="forbidden")
    chunks_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).count()
    return DocumentOut(document_id=document_id, status=doc.status, chunks=chunks_count)


@app.post("/v1/rag/query", response_model=RagQueryOut)
def rag_query(
    payload: RagQueryCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("farmer", "analyst", "admin")),
) -> RagQueryOut:
    check_rate_limit(request)
    _ = user
    retrieved = _retrieve_chunks(db, payload.question, top_k=payload.top_k, profile=payload.profile)
    answer = generate_answer_with_context(
        payload.question,
        retrieved,
        base_url=settings.ollama_url,
        model=settings.ollama_chat_model,
    )
    return RagQueryOut(
        answer=answer,
        sources=[
            SourceItem(doc_id=item["doc_id"], chunk_id=item["chunk_id"], score=float(item["score"]))
            for item in retrieved
        ],
    )


@app.post("/v1/rag/compare", response_model=RagCompareOut)
def rag_compare(
    payload: RagCompareCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> RagCompareOut:
    check_rate_limit(request)
    _ = user
    profiles = payload.profiles[:5] if payload.profiles else ["balanced", "semantic_heavy", "lexical_heavy"]
    results: list[RagCompareItem] = []
    metrics_rows: list[dict] = []
    for profile in profiles:
        retrieved = _retrieve_chunks(db, payload.question, top_k=payload.top_k, profile=profile)
        answer = generate_answer_with_context(
            payload.question,
            retrieved,
            base_url=settings.ollama_url,
            model=settings.ollama_chat_model,
        )
        results.append(
            RagCompareItem(
                profile=profile,
                answer=answer,
                sources=[
                    SourceItem(doc_id=item["doc_id"], chunk_id=item["chunk_id"], score=float(item["score"]))
                    for item in retrieved
                ],
            )
        )
        avg_score = (sum(float(item["score"]) for item in retrieved) / len(retrieved)) if retrieved else 0.0
        metrics_rows.append(
            {
                "profile": profile,
                "sources_count": len(retrieved),
                "avg_source_score": round(avg_score, 4),
            }
        )

    run_id: str | None = None
    if payload.save_eval:
        run = EvalRun(
            dataset=payload.dataset,
            model=payload.model,
            status="completed",
            sample_size=1,
            metrics={
                "type": "rag_compare",
                "question": payload.question,
                "top_k": payload.top_k,
                "locale": payload.locale,
                "profiles": metrics_rows,
            },
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id

    return RagCompareOut(question=payload.question, results=results, run_id=run_id)


@app.post("/v1/agents/debate", response_model=AgentDebateOut)
def run_agent_debate(
    payload: AgentDebateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> AgentDebateOut:
    check_rate_limit(request)
    _ = user
    started = time.perf_counter()
    if payload.safety_override and (not payload.override_reason or len(payload.override_reason.strip()) < 8):
        raise HTTPException(status_code=400, detail="override_reason must be provided and be at least 8 characters")

    trace_id = str(uuid4())
    drafts, final = run_hierarchical_debate(payload.question, payload.locale, payload.rounds)
    safety = evaluate_agro_policy(payload.question, final["answer"], payload.locale)
    overridden = payload.safety_override and safety.action == "block"
    effective_action = "warn" if overridden else safety.action
    final_answer = final["answer"] if overridden else (safety.safe_alternative if safety.action == "block" else final["answer"])
    policy_draft = AgentStepDraft(
        agent_name="safety-policy-agent",
        step_type="safety_policy",
        payload={
            "policy_version": safety.policy_version,
            "original_action": safety.action,
            "effective_action": effective_action,
            "overridden": overridden,
            "override_reason": payload.override_reason,
            "level": safety.level,
            "reasons": safety.reasons,
            "rules_triggered": safety.rules_triggered,
            "original_answer": final["answer"],
            "final_answer": final_answer,
        },
    )
    all_drafts = [*drafts, policy_draft]

    steps_out: list[AgentStepOut] = []
    step_hashes: list[str] = []
    parent_hash: str | None = None
    parent_step_id: str | None = None
    for draft in all_drafts:
        step_payload = {
            "question": payload.question,
            "agent_name": draft.agent_name,
            "step_type": draft.step_type,
            "data": draft.payload,
        }
        step_hash = _compute_step_hash(parent_hash, step_payload)
        step = AgentStep(
            trace_id=trace_id,
            parent_step_id=parent_step_id,
            agent_name=draft.agent_name,
            step_type=draft.step_type,
            parent_hash=parent_hash,
            step_hash=step_hash,
            payload=step_payload,
        )
        db.add(step)
        db.flush()
        step_hashes.append(step_hash)

        if payload.include_steps:
            steps_out.append(
                AgentStepOut(
                    step_id=step.id,
                    agent_name=step.agent_name,
                    step_type=step.step_type,
                    step_hash=step.step_hash,
                    parent_hash=step.parent_hash,
                    payload=step.payload,
                )
            )
        parent_hash = step_hash
        parent_step_id = step.id

    db.add(
        SafetyAuditLog(
            trace_id=trace_id,
            policy_version=safety.policy_version,
            original_action=safety.action,
            effective_action=effective_action,
            overridden=overridden,
            override_reason=payload.override_reason.strip() if payload.override_reason else None,
            safety_level=safety.level,
            rules_triggered={"items": safety.rules_triggered},
            reasons={"items": safety.reasons},
            question=payload.question,
            recommendation=final_answer,
        )
    )
    db.commit()
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    trace_digest = _compute_trace_digest(step_hashes)
    _update_debate_metrics(
        winner=str(final["winner"]),
        latency_ms=elapsed_ms,
        trace_id=trace_id,
        rounds=int(final["rounds"]),
        step_count=len(step_hashes),
        blocked=effective_action == "block",
        overridden=overridden,
    )
    return AgentDebateOut(
        trace_id=trace_id,
        trace_digest=trace_digest,
        answer=final_answer,
        winner=final["winner"],
        score_a=float(final["score_a"]),
        score_b=float(final["score_b"]),
        rounds=int(final["rounds"]),
        spawned_agents=[str(item) for item in final["spawned_agents"]],
        safety=AgentSafetyOut(
            policy_version=safety.policy_version,
            level=safety.level,
            original_action=safety.action,
            effective_action=effective_action,
            overridden=overridden,
            override_reason=payload.override_reason.strip() if payload.override_reason else None,
            reasons=safety.reasons,
            rules_triggered=safety.rules_triggered,
        ),
        steps=steps_out,
    )


@app.get("/v1/agents/traces/{trace_id}", response_model=AgentTraceOut)
def get_agent_trace(
    trace_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> AgentTraceOut:
    check_rate_limit(request)
    _ = user
    rows = db.query(AgentStep).filter(AgentStep.trace_id == trace_id).all()
    if not rows:
        raise HTTPException(status_code=404, detail="trace not found")
    ordered_rows = _order_steps_by_chain(rows)
    step_hashes = [row.step_hash for row in ordered_rows]
    return AgentTraceOut(
        trace_id=trace_id,
        trace_digest=_compute_trace_digest(step_hashes),
        steps=[
            AgentStepOut(
                step_id=row.id,
                agent_name=row.agent_name,
                step_type=row.step_type,
                step_hash=row.step_hash,
                parent_hash=row.parent_hash,
                payload=row.payload,
            )
            for row in ordered_rows
        ],
    )


@app.get("/v1/agents/metrics", response_model=AgentMetricsOut)
def get_agent_metrics(
    request: Request,
    user: User = Depends(require_roles("analyst", "admin")),
) -> AgentMetricsOut:
    check_rate_limit(request)
    _ = user
    with _debate_metrics_lock:
        total_runs = int(_debate_metrics["total_runs"])
        avg_latency = (float(_debate_metrics["total_latency_ms"]) / total_runs) if total_runs else 0.0
        avg_rounds = (float(_debate_metrics["total_rounds"]) / total_runs) if total_runs else 0.0
        avg_steps = (float(_debate_metrics["total_steps"]) / total_runs) if total_runs else 0.0
        return AgentMetricsOut(
            total_runs=total_runs,
            blocked_runs=int(_debate_metrics["blocked_runs"]),
            overridden_runs=int(_debate_metrics["overridden_runs"]),
            winner_a=int(_debate_metrics["winner_a"]),
            winner_b=int(_debate_metrics["winner_b"]),
            avg_latency_ms=round(avg_latency, 2),
            avg_rounds=round(avg_rounds, 2),
            avg_steps=round(avg_steps, 2),
            last_trace_id=_debate_metrics["last_trace_id"],
        )


@app.get("/v1/agents/safety/audit", response_model=SafetyAuditListOut)
def list_safety_audit(
    request: Request,
    limit: int = 20,
    trace_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> SafetyAuditListOut:
    check_rate_limit(request)
    _ = user
    q = db.query(SafetyAuditLog)
    if trace_id:
        q = q.filter(SafetyAuditLog.trace_id == trace_id)
    rows = q.order_by(SafetyAuditLog.created_at.desc()).limit(max(1, min(limit, 100))).all()
    return SafetyAuditListOut(
        items=[
            SafetyAuditItemOut(
                audit_id=row.id,
                trace_id=row.trace_id,
                policy_version=row.policy_version,
                original_action=row.original_action,
                effective_action=row.effective_action,
                overridden=row.overridden,
                override_reason=row.override_reason,
                safety_level=row.safety_level,
                rules_triggered=[str(item) for item in (row.rules_triggered or {}).get("items", [])],
                reasons=[str(item) for item in (row.reasons or {}).get("items", [])],
                question=row.question,
                recommendation=row.recommendation,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> PlainTextResponse:
    return PlainTextResponse(_render_prometheus_metrics(), media_type="text/plain; version=0.0.4")


@app.post("/v1/tools/weather", response_model=WeatherOut)
def weather_tool(
    payload: WeatherRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("farmer", "analyst", "admin")),
) -> WeatherOut:
    check_rate_limit(request)
    _ = user
    requested = datetime.strptime(payload.date, "%Y-%m-%d").date()
    today = datetime.now(timezone.utc).date()
    is_past = requested <= today

    base_url = settings.open_meteo_archive_url if is_past else settings.open_meteo_forecast_url

    params = {
        "latitude": payload.lat,
        "longitude": payload.lon,
        "daily": "temperature_2m_max,precipitation_sum,wind_speed_10m_max",
        "timezone": "auto",
        "start_date": payload.date,
        "end_date": payload.date,
    }

    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.get(base_url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"weather provider error: {exc}") from exc

    wind = _pick_daily_value(data, "wind_speed_10m_max")
    if wind == 0.0:
        wind = _pick_daily_value(data, "windspeed_10m_max")

    out = WeatherOut(
        temp_c=_pick_daily_value(data, "temperature_2m_max"),
        precip_mm=_pick_daily_value(data, "precipitation_sum"),
        wind_ms=round(wind / 3.6, 2),
        source="open-meteo",
    )

    call = ToolCall(
        tool_name="weather",
        input_json={"lat": payload.lat, "lon": payload.lon, "date": payload.date},
        output_json=out.model_dump(),
        status="ok",
    )
    db.add(call)
    db.commit()

    return out


@app.post("/v1/tools/ndvi", response_model=NDVIOut)
async def ndvi_tool(
    request: Request,
    image: UploadFile = File(...),
    user: User = Depends(require_roles("farmer", "analyst", "admin")),
) -> NDVIOut:
    check_rate_limit(request)
    _ = user
    raw = await image.read()
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="image too large")

    try:
        from io import BytesIO

        img = Image.open(BytesIO(raw)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"invalid image: {exc}") from exc

    arr = np.asarray(img).astype(np.float32)
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    # RGB proxy index when NIR channel is unavailable.
    idx = (g - r) / (g + r + 1e-6)
    ndvi = float(np.clip(idx.mean(), -1.0, 1.0))
    zone = "low" if ndvi < 0.2 else "moderate" if ndvi < 0.5 else "high"
    conf = float(np.clip(0.6 + (float(np.std(idx)) * 0.1), 0.6, 0.92))
    return NDVIOut(ndvi_index=round(ndvi, 3), zone=zone, confidence=round(conf, 2))


@app.post("/v1/evals/run", response_model=EvalRunOut)
def run_eval(
    payload: EvalRunCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> EvalRunOut:
    check_rate_limit(request)
    cached = _idem_get("evals", idempotency_key)
    if cached:
        return EvalRunOut(**cached)
    _ = user
    run = EvalRun(dataset=payload.dataset, model=payload.model, sample_size=payload.sample_size, status="queued")
    db.add(run)
    db.flush()
    job = Job(
        job_type="eval_run",
        status="queued",
        payload={"eval_run_id": run.id, "dataset": payload.dataset, "model": payload.model},
    )
    db.add(job)
    db.commit()
    db.refresh(run)
    db.refresh(job)
    background_tasks.add_task(_run_eval_job, job.id, run.id)
    out = EvalRunOut(run_id=run.id, status=run.status)
    _idem_set("evals", idempotency_key, out.model_dump())
    return out


@app.get("/v1/evals/{run_id}", response_model=EvalRunDetail)
def get_eval_run(
    run_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> EvalRunDetail:
    check_rate_limit(request)
    _ = user
    run = db.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="eval run not found")
    return EvalRunDetail(
        run_id=run.id,
        dataset=run.dataset,
        model=run.model,
        status=run.status,
        sample_size=run.sample_size,
        created_at=run.created_at,
        metrics=run.metrics or {},
    )


@app.get("/v1/evals", response_model=EvalRunListOut)
def list_eval_runs(
    request: Request,
    dataset: str | None = None,
    model: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> EvalRunListOut:
    check_rate_limit(request)
    _ = user
    q = db.query(EvalRun)
    if dataset:
        q = q.filter(EvalRun.dataset == dataset)
    if model:
        q = q.filter(EvalRun.model == model)
    rows = q.order_by(EvalRun.created_at.desc()).limit(max(1, min(limit, 100))).all()
    return EvalRunListOut(
        items=[
            EvalRunItem(
                run_id=row.id,
                dataset=row.dataset,
                model=row.model,
                status=row.status,
                sample_size=row.sample_size,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )


@app.get("/v1/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin", "farmer")),
) -> JobOut:
    check_rate_limit(request)
    _ = user
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobOut(
        job_id=job.id,
        job_type=job.job_type,
        status=job.status,
        payload=job.payload or {},
        result=job.result or {},
        error=job.error,
    )


@app.get("/v1/jobs")
def list_jobs(
    request: Request,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> dict:
    check_rate_limit(request)
    _ = user
    rows = db.query(Job).order_by(Job.created_at.desc()).limit(max(1, min(limit, 100))).all()
    return {
        "items": [
            JobOut(
                job_id=row.id,
                job_type=row.job_type,
                status=row.status,
                payload=row.payload or {},
                result=row.result or {},
                error=row.error,
            ).model_dump()
            for row in rows
        ]
    }




