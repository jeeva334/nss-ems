# Manpower Outsourcing Employee Management Portal

Status: **Stage 1 complete** (shell, health checks, DB connectivity, migrations wiring).
Not yet implemented: auth, RBAC, users, invitations, clients, assignments, audit logs.

## Local setup
Backend (Python 3.12, PostgreSQL 16):
    cd backend && python -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt && cp .env.example .env
    alembic upgrade head
    uvicorn app.main:app --reload --port 8000
    python -m pytest -q
Frontend (Node 22):
    cd frontend && npm install && npm run dev      # http://localhost:5173
    npm test && npm run build

## Endpoints
GET /api/v1/health/live, GET /api/v1/health/ready (checks PostgreSQL).

## Architecture notes
Modular monolith. Routes thin; logic in services (later stages). JSON logs with
X-Request-ID correlation. Migrations are run explicitly, never on startup.
