# AgroAgent

[![CI](https://github.com/mozaika228/agroagent/actions/workflows/ci.yml/badge.svg)](https://github.com/mozaika228/agroagent/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](apps/api)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](apps/web)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

AI-agent platform for agriculture in West Kazakhstan.

## What Already Works
- JWT auth + RBAC (`farmer`, `analyst`, `admin`)
- Fullstack dashboard UI (auth, chat, document upload, RAG query/compare, eval history)
- Hybrid RAG retrieval: pgvector cosine + Postgres FTS + BM25 re-rank
- Async jobs for document ingestion and eval runs
- Redis-backed rate limiting (with in-memory fallback)
- Weather tool (Open-Meteo), NDVI RGB-proxy tool
- Eval tracking with `run_id`, list, and detail endpoints
- Dynamic hierarchical debate (root spawns sub-agents by query) + verifiable hash-chain viewer in web UI
- Debate observability metrics endpoint (`total_runs`, winner split, average latency, avg rounds, avg steps)
- Safety policy layer for debate answers (`allow/warn/block`) with explainable triggered rules
- CI with web lint/build + API tests + coverage XML artifact

## Architecture At a Glance
- `apps/web`: Next.js UI console
  - componentized panels in `apps/web/app/components`
- `apps/api`: FastAPI orchestration, auth, tools, RAG, evals
- `infra/db`: SQL migrations, seed, backup/restore scripts
- `docs/`: architecture, API contracts, backlog, eval plan

Detailed docs:
- `docs/architecture.md`
- `docs/api-contracts.md`
- `docs/eval-plan.md`
- `docs/mvp-backlog.md`

## Quick Start
1. Start infra:
   - `docker compose -f infra/docker/docker-compose.yml up -d postgres ollama`
2. API setup:
   - `cd apps/api`
   - `copy .env.example .env`
   - set secure `JWT_SECRET` and DB settings in `.env`
   - optional: set `REDIS_URL` to enable distributed rate limiting
   - `pip install -r requirements.txt`
   - `alembic -c alembic.ini upgrade head`
   - optional seed:
     - `psql -h localhost -p 5432 -U agro -d agroagent -f ../../infra/db/seed/001_seed.sql`
   - `uvicorn app.main:app --reload --port 8000`
3. Web setup:
   - `cd apps/web`
   - `pnpm install`
   - `pnpm dev`
4. Optional local models:
   - `ollama pull llama3.1:8b`
   - `ollama pull nomic-embed-text`

## Demo Requests
Auth:
```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@agroagent.local","password":"pass1234"}'
```

RAG query:
```bash
curl -X POST http://localhost:8000/v1/rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT>" \
  -d '{"question":"what to sow in Uralsk in May?","top_k":5,"profile":"balanced"}'
```

RAG compare:
```bash
curl -X POST http://localhost:8000/v1/rag/compare \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT>" \
  -d '{"question":"fertilizer strategy for spring wheat","profiles":["balanced","semantic_heavy","lexical_heavy"],"save_eval":true}'
```

## API Surface (Main)
- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `GET /v1/auth/me`
- `POST /v1/chat/sessions`
- `POST /v1/chat/messages`
- `POST /v1/documents`
- `GET /v1/documents/{id}`
- `POST /v1/rag/query`
- `POST /v1/rag/compare`
- `POST /v1/agents/debate`
- `GET /v1/agents/traces/{trace_id}`
- `GET /v1/agents/metrics`
- `GET /v1/agents/safety/audit`
- `POST /v1/agents/safety/evals/run`
- `GET /metrics`
- `POST /v1/tools/weather`
- `POST /v1/tools/ndvi`
- `POST /v1/evals/run`
- `GET /v1/evals`
- `GET /v1/evals/{run_id}`
- `GET /v1/jobs`
- `GET /v1/jobs/{job_id}`

## Quality
- API tests: `python -m pytest apps/api/tests --cov=apps/api/app`
- Type/lint/build checks via GitHub Actions CI

## Roadmap
- Production NDVI pipeline with calibrated satellite/sensor channels
- LangGraph planner/researcher/agronomist/verifier execution path
- Multilingual retrieval optimization (RU/KZ/EN benchmarks)
- Telegram and mobile clients with degraded/offline modes
- Observability dashboard for latency, tool reliability, safety metrics

## Backup / Restore
- Backup: `pwsh infra/db/scripts/backup.ps1`
- Restore: `pwsh infra/db/scripts/restore.ps1 -BackupFile <path>`

## Contributing
See `CONTRIBUTING.md`.

## License
MIT (`LICENSE`).
