# Manpower Outsourcing Employee Management Portal

Status: **Stage 5 complete** (hardening, audit viewer, E2E) on top of Stages 1-4.
Not yet implemented: Stage 6 (production build config, deployment/backup/rollback docs, least-privilege DB role, `_headers`).

## Stage 5: hardening, audit, E2E
- **Audit viewer**: `GET /audit-logs` (Admin only; filter by action prefix, actor, target, date range; paginated) and an
  *Audit Log* page. Metadata is scrubbed of secrets before it is stored.
- **Hardening** (see `docs/security.md` for the full matrix): security headers, Origin check, body-size cap, sanitised
  request ids, structured access log (method/path/status/duration; never query strings), clean 503 on DB outage, generic
  500 with correlation id, and a database-backed rate limiter shared across workers (migration `rate_limit_events`).
- **Authorization sweep**: tests iterate every route in the OpenAPI schema and assert 401 anonymous / 403 non-admin.
- **Dependencies upgraded** (FastAPI 0.159/Starlette 1.9, react-router 7, Vite 8, Vitest 5, Tailwind 4); both audits clean.
- **E2E** (`cd frontend && npm run test:e2e`): runs the real React app (jsdom) against a real API process and PostgreSQL,
  no mocks, driving the UI through login, user creation, Employee IDs, invitations, activation, Manager/client assignment,
  Supervisor mapping and client assignment, and the rejection cases. It RESETS the `manpower_e2e` database each run
  (override with `E2E_DATABASE_URL`). **This is not a real-browser test**: Playwright could not be used because browser
  downloads were blocked in the build environment. Rendering/layout/CSS and browser-specific behaviour are not covered.
- Housekeeping job: `python -m scripts.purge_expired`.

## Clients & assignments (Stage 4)
Endpoints: `GET/POST /clients`, `GET/PATCH /clients/{id}`, `PATCH /clients/{id}/status`, `PUT /clients/{id}/manager`,
`PUT /users/{id}/manager` (map Supervisor to Manager), `PUT /users/{id}/client` (assign Supervisor's client),
`GET /users/{id}/assignments` (current + history). All mutations are Admin-only.
Resource-level reads: Admin sees all clients; a Manager lists/views only their own (403 otherwise); a Supervisor may
view only their assigned client (colleagues are not exposed).

Decisions / rules
- A client may exist without a Manager (unassigned); it can only ever have one (single column). Client code is
  normalised to upper case and immutable.
- **Reassignment (option 1, "block")**: moving or removing a client's Manager needs `reassign: true` and is refused
  (409 `has_dependent_assignments`, listing the Supervisors) while any Supervisor is assigned to that client. The Admin
  resolves explicitly by moving/clearing those Supervisors first. Same rule for deactivating a client.
- Supervisor Manager change is a separate explicit action; if the Supervisor has a client, `clear_client: true` is
  required (409 `has_client_assignment` otherwise). The client endpoint never accepts a Manager: it is taken from the
  stored mapping and the client is validated against it, even if the UI already filters the options.
- Pending/inactive Managers and inactive clients cannot be assigned. Deactivating a Supervisor unmaps them and records
  `supervisor_unmapped_on_deactivation` in history + audit (resolves the Stage 3 limitation).
- Concurrency: assignment writes lock the client row (`FOR UPDATE`), the manager (`FOR SHARE`) and the assignment
  (`FOR NO KEY UPDATE`, which avoids deadlocks with the FK checks). Any remaining DB conflict/deadlock is converted to a
  clean 409 (`conflict`). The composite foreign keys remain the last line of defence.
- Manager UI: assign *unassigned* clients, remove clients, map/unmap Supervisors. Moving a client that already has a
  Manager happens only from the client page (explicit reassignment dialog).

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
- Rate limiting is now database-backed and shared across workers (check-then-insert, so bursts can slightly exceed the limit).
- Behind Render's proxy, run uvicorn with `--proxy-headers` so client IPs are correct.
- Resend delivery path is implemented but was NOT exercised against the real Resend API (no key in this environment); only the failure/success handling is tested via a fake sender.
- Reactivating a Supervisor does not restore their old assignment; the Admin re-maps them (history shows what was removed).
- Manager/Supervisor-facing screens for clients are not built; their backend read access exists and is tested, but the UI nav is Admin-only.
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
