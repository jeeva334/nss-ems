# Manpower Outsourcing Employee Management Portal

Status: **Stage 2 complete** (schema + migration, authentication, RBAC primitives, bootstrap).
Not yet implemented: user/client CRUD endpoints, invitations & activation, assignment endpoints/UI, email, deployment docs.

## Auth architecture (decision)
Server-side sessions in PostgreSQL. Cookie `mp_session` (HttpOnly, Secure in production, SameSite configurable)
holds a random token; only its SHA-256 is stored. New session on every login (rotation); idle (60 min) and
absolute (12 h) expiry; sessions revoked on logout and (via `revoke_user_sessions`) on deactivation.
CSRF: per-session token returned by `/auth/login` and `/auth/me`, required in `X-CSRF-Token` on every non-GET request.
Passwords: Argon2id. Login failures are rate limited (in-process; see limitations) and audited.

## First Admin (one-time)
    cd backend && python -m scripts.bootstrap_admin     # refuses if any Admin exists; no public endpoint

## Database integrity (enforced in PostgreSQL)
Employee IDs from sequence via `next_employee_id()`; immutable via trigger. Composite FKs guarantee: client manager
is a MANAGER; assignment supervisor is a SUPERVISOR; a supervisor's client always belongs to the supervisor's manager.
Changing a client's manager while supervisors depend on it is rejected by the DB (service must resolve first, Stage 4).
Not yet DB-enforced: manager/client *active* status (service-layer check in Stage 4).

## Known limitations
- Login rate limiter is per-process memory; use a shared store if running multiple workers.
- Behind Render's proxy, run uvicorn with `--proxy-headers` so client IPs are correct.
- Cross-site frontend/API hosting needs COOKIE_SAMESITE=none + HTTPS.

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
