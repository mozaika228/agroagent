from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    user_id: str | None = None
    locale: str = "ru"


class ChatSessionOut(BaseModel):
    session_id: str
    created_at: datetime


class Attachment(BaseModel):
    type: str
    id: str


class ChatMessageCreate(BaseModel):
    session_id: str
    text: str
    attachments: list[Attachment] = Field(default_factory=list)
    locale: str = "ru"


class SourceItem(BaseModel):
    doc_id: str
    chunk_id: str
    score: float


class ToolUsed(BaseModel):
    name: str
    status: str


class SafetyInfo(BaseModel):
    level: str
    notes: list[str]


class ChatMessageOut(BaseModel):
    message_id: str
    answer: str
    sources: list[SourceItem]
    tools_used: list[ToolUsed]
    safety: SafetyInfo
    trace_id: str


class RagQueryCreate(BaseModel):
    question: str
    top_k: int = 5
    locale: str = "ru"
    profile: str = "balanced"


class RagQueryOut(BaseModel):
    answer: str
    sources: list[SourceItem]


class RagCompareCreate(BaseModel):
    question: str
    top_k: int = 5
    locale: str = "ru"
    profiles: list[str] = Field(default_factory=lambda: ["balanced", "semantic_heavy", "lexical_heavy"])
    save_eval: bool = True
    dataset: str = "rag_compare_ad_hoc"
    model: str = "retriever_hybrid_v1"


class RagCompareItem(BaseModel):
    profile: str
    answer: str
    sources: list[SourceItem]


class RagCompareOut(BaseModel):
    question: str
    results: list[RagCompareItem]
    run_id: str | None = None


class WeatherRequest(BaseModel):
    lat: float
    lon: float
    date: str


class WeatherOut(BaseModel):
    temp_c: float
    precip_mm: float
    wind_ms: float
    source: str


class NDVIOut(BaseModel):
    ndvi_index: float
    zone: str
    confidence: float


class EvalRunCreate(BaseModel):
    dataset: str
    model: str
    sample_size: int = 50


class EvalRunOut(BaseModel):
    run_id: str
    status: str


class EvalRunItem(BaseModel):
    run_id: str
    dataset: str
    model: str
    status: str
    sample_size: int
    created_at: datetime


class EvalRunDetail(EvalRunItem):
    metrics: dict[str, Any]


class EvalRunListOut(BaseModel):
    items: list[EvalRunItem]


class DocumentOut(BaseModel):
    document_id: str
    status: str
    chunks: int | None = None


class ErrorOut(BaseModel):
    detail: str
    meta: dict[str, Any] | None = None


class AuthRegisterCreate(BaseModel):
    email: str
    password: str
    locale: str = "ru"
    role: str = "farmer"


class AuthLoginCreate(BaseModel):
    email: str
    password: str


class AuthTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


class JobOut(BaseModel):
    job_id: str
    job_type: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any]
    error: str | None = None

