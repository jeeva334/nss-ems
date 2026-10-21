# Manpower Outsourcing Employee Management Portal

Status: **Stage 3 complete** (users, invitations, activation) on top of Stage 2 (schema, auth, RBAC).
Not yet implemented: client management, assignment endpoints/UI, deployment docs, e2e browser tests.

## Users & invitations (Stage 3)
Admin-only endpoints: `GET/POST /users`, `GET/PATCH /users/{id}`, `PATCH /users/{id}/status`,
`POST /users/{id}/invitations`, `POST /users/{id}/invitations/revoke`; public `POST /auth/activate`.
- Account + hashed invitation are committed **before** any email is attempted (equivalent to an outbox for this
  scale). A provider failure keeps the account PENDING, stores a sanitized error code, and the Admin can resend.
  The UI reports success only when the provider accepted the request.
- Links use a URL *fragment* (`/activate#token=...`) so the token never reaches server logs or Referer headers.
- One live invitation per user (DB partial unique index); resend revokes older tokens; redemption locks the row
  (`SELECT … FOR UPDATE`) so concurrent redemption has exactly one winner. Resends limited to 5/hour/user.
- Email: `EMAIL_PROVIDER=resend` + `RESEND_API_KEY` in production (enforced at startup). In development,
  `dev_outbox` writes messages to `backend/.dev_outbox/` (gitignored, refuses to run in production).
- Role and Employee ID cannot be changed via PATCH (422). Admins cannot deactivate themselves or the last active
  Admin; a Manager with clients/supervisors cannot be deactivated until reassigned. Deactivation revokes sessions
  and invitations. Reactivating a never-activated account returns it to PENDING.

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
- Resend delivery path is implemented but was NOT exercised against the real Resend API (no key in this environment); only the failure/success handling is tested via a fake sender.
- Deactivating a Supervisor leaves its assignment row in place (resolved in Stage 4).
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
