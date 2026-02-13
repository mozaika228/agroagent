# Contributing

## Workflow
1. Create a feature branch from `main`.
2. Keep changes scoped to one concern (UI, API, infra, docs).
3. Run local checks before opening PR.
4. Open PR with context, screenshots (for UI), and test evidence.

## Local Checks
- API tests:
  - `cd apps/api`
  - `python -m pytest tests --cov=app`
- Web lint/build:
  - `cd apps/web`
  - `pnpm lint`
  - `pnpm build`

## PR Expectations
- Clear title and description.
- Mention impacted endpoints/files.
- Add/update docs when behavior changes.
- Add tests for bug fixes or new logic.

## Coding Guidelines
- Keep functions small and explicit.
- Prefer typed request/response models.
- For API changes, update `docs/api-contracts.md`.
- For architecture-level decisions, update `docs/architecture.md`.
