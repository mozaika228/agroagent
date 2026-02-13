# Architecture (MVP)

- `apps/web`: farmer and analyst UI
- `apps/api`: FastAPI endpoints and agent orchestration boundary
- `packages/ai-core`: LangGraph nodes + prompts + safety + eval
- `PostgreSQL + pgvector`: chat, docs, chunks, evals
- `Ollama`: local model runtime

Pipeline:
1. Planner classifies intent.
2. Researcher calls tools + retrieval.
3. Agronomist drafts recommendation.
4. Verifier enforces safety policy.

Retrieval:
- Hybrid candidate generation: pgvector cosine + lexical full-text search.
- Re-ranking: weighted score (vector similarity + BM25 score).

Operational hardening:
- JWT + RBAC for all non-health endpoints.
- In-memory rate limiter (per-IP, per-minute window).
- Structured request logging with request ID and latency.
- Background jobs table for async ingestion/eval execution status.

