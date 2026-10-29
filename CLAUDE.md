# FolioLens: instructions for Claude Code

FolioLens is a portfolio analytics web app for Indian financial advisors. Read `README.md` for the
overview, `docs/PRD.md` for the spec, `docs/ARCHITECTURE.md` and `docs/DECISIONS.md` before changing code.

## Status
V1 is built: backend, analytics engine, ingestion, insights, frontend, Docker, CI and the AWS guide.
V1.1 (engine 1.1.0): profit attribution, index comparison (PME), tax estimates, options to discuss,
plain-English summary, light theme, guided steps and a client report.
V1.2 (engine 1.2.0): risk profiling + suitability, goal planning, tax-aware rebalancing (client_plans table).
Next candidates: corporate-action adjustments, NSDL/CDSL CAS, blended benchmark, real data loads.

## Who you're working with
Dakshin, a BTech student; this is his flagship project for fintech roles. He must be able to explain
every change: after each change, explain what and why in simple English, and add interview-relevant
notes to `docs/LEARNING_NOTES.md`.

## Non-negotiable principles
1. Verified calculations first, transparent evidence second, AI explanations third.
2. Transactions are the source of truth; holdings are derived (no holdings table).
3. Never replace missing data with zero; mark it incomplete and say so in `data_quality`.
4. Every report stores `calc_version`; bump `CALC_VERSION` in `app/config.py` when a formula changes.
5. Every private route checks ownership and returns 404 for other users' resources; add a test.
6. `app/analytics` and `app/reports/engine.py` stay pure: no DB, network or LLM imports.
7. The LLM only explains; its numbers are validated; templates are the fallback.
8. Secrets only in `.env` / SSM. Never commit or print them.

## Commands
```bash
cd backend && source .venv/bin/activate
pytest                      # all tests (needs PostgreSQL; set TEST_DATABASE_URL if not default)
ruff check app tests && ruff format app tests && mypy app
alembic revision --autogenerate -m "describe change"   # after model changes
cd ../frontend && npm run build
docker compose up --build   # whole stack on http://localhost:8080
```

## Conventions
- Small commits; Dakshin commits and pushes himself.
- Record new decisions in `docs/DECISIONS.md`.
- Tests and linters must pass before saying a change is done.
