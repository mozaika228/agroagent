# API Contracts (v1)

Core entities:
- Session
- Message
- Document
- DocumentChunk
- ToolCall
- EvalRun
- Job
- User/Auth

Base URL:
- `http://localhost:8000`
- Auth: `Authorization: Bearer <JWT>` for non-health endpoints.

See `apps/api/app/main.py` for current request/response models.

RAG flow:
1. Upload PDF/TXT via `POST /v1/documents`.
2. Server extracts text, chunks it, creates embeddings, stores in `document_chunks`.
3. Query via `POST /v1/rag/query` or chat endpoint to get grounded answer + citations.
4. Compare retriever profiles via `POST /v1/rag/compare`.
5. With `save_eval=true`, compare results are persisted to `eval_runs.metrics` and response includes `run_id`.
6. History endpoints:
- `GET /v1/evals?dataset=...&model=...&limit=...`
- `GET /v1/evals/{run_id}`

Retriever profiles:
- `balanced` (default)
- `semantic_heavy`
- `lexical_heavy`

Auth:
- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `GET /v1/auth/me`

Jobs:
- `GET /v1/jobs`
- `GET /v1/jobs/{job_id}`

