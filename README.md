# AgroAgent

AI-agent platform for agriculture in West Kazakhstan (MVP scaffold).

## Stack
- Web: Next.js + TypeScript
- API: FastAPI + Pydantic + SQLAlchemy
- AI runtime: Ollama (local)
- DB: PostgreSQL + pgvector
- Migrations: Alembic
- Monorepo: pnpm + turbo

## Security
- JWT auth (`/v1/auth/register`, `/v1/auth/login`, `/v1/auth/me`)
- RBAC roles: `farmer`, `analyst`, `admin`
- In-memory rate limiting per IP
- Upload validation (size and file extension)

## Quick start
1. Start infra:
   - `docker compose -f infra/docker/docker-compose.yml up -d postgres ollama`
2. API setup:
   - `cd apps/api`
   - `copy .env.example .env` and set secure values
   - `pip install -r requirements.txt`
   - `alembic -c alembic.ini upgrade head`
   - seed demo data (optional):
     - `psql -h localhost -p 5432 -U agro -d agroagent -f ../../infra/db/seed/001_seed.sql`
   - `uvicorn app.main:app --reload --port 8000`
   - set secure env values (`JWT_SECRET`, `WEB_ORIGINS`, DB creds) before production deploy
3. Web setup:
   - `cd apps/web`
   - `pnpm install`
   - `pnpm dev`
4. Pull local models (optional but recommended):
   - `ollama pull llama3.1:8b`
   - `ollama pull nomic-embed-text`

## MVP endpoints
- `POST /v1/chat/sessions`
- `POST /v1/chat/messages`
- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `GET /v1/auth/me`
- `POST /v1/documents`
- `GET /v1/documents/{id}`
- `POST /v1/rag/query`
- `POST /v1/rag/compare`
- `POST /v1/tools/weather`
- `POST /v1/tools/ndvi`
- `POST /v1/evals/run`
- `GET /v1/evals`
- `GET /v1/evals/{run_id}`
- `GET /v1/jobs`
- `GET /v1/jobs/{job_id}`

`/v1/rag/compare` can persist A/B outcomes to `eval_runs` when `save_eval=true`.

## Backup / Restore
- Backup: `pwsh infra/db/scripts/backup.ps1`
- Restore: `pwsh infra/db/scripts/restore.ps1 -BackupFile <path>`
