# Security notes (state after Stage 5)

## What is enforced, and where
| Concern | Mechanism | Verified by |
|---|---|---|
| AuthN on every protected route | `get_auth` session dependency | `test_every_protected_route_rejects_anonymous` (sweeps **every** route from the OpenAPI schema) |
| Role authorization | `require_roles` on every admin route | `test_every_admin_route_forbidden_for_non_admins` (Manager + Supervisor, every route) |
| Resource-level authorization | Managers see only their clients; Supervisors only their assigned client | `test_assignments.py` |
| CSRF | per-session token in `X-CSRF-Token`, all non-GET | `test_state_changing_routes_all_enforce_csrf` |
| Cross-origin writes | `Origin` must be in `CORS_ORIGINS` for POST/PUT/PATCH/DELETE | `test_origin_check_on_state_changing_requests` |
| Passwords | Argon2id, policy enforced server-side, never logged/echoed | `test_security.py`, `test_validation_errors_never_echo_secrets` |
| Sessions | server-side, hashed id, rotation, idle + absolute expiry, revoked on logout/deactivation | `test_auth.py` |
| Invitations | random, hashed, single-use, expiring, one live per user, fragment URL | `test_users.py` |
| Brute force | DB-backed sliding-window limiter (shared by all workers); keys stored hashed | `test_rate_limiter_*` |
| Data integrity | composite FKs, unique/check constraints, immutable Employee ID trigger | `test_db_constraints.py`, concurrency tests |
| Audit | every admin/security action; secrets scrubbed before persisting | `test_scrubber_*`, `test_full_flow_audit_contains_no_secrets` |
| Error leakage | generic 500/503 with correlation id; DB errors never returned; 422 never echoes input | `test_unhandled_error_*`, `test_database_outage_*` |
| Transport headers | nosniff, DENY framing, no-referrer, no-store, CSP for API, HSTS (production) | `test_security_headers_present`, `test_hsts_in_production` |
| Request abuse | 64 KB body cap (Content-Length), sanitised request ids | `test_oversized_body_rejected`, `test_request_id_is_sanitised` |
| Supply chain | `pip-audit` and `npm audit` both report 0 known vulnerabilities | run at the end of Stage 5 |

## Adding an endpoint
The authorization sweep derives its route list from OpenAPI. A new route that forgets authentication fails
`test_every_protected_route_rejects_anonymous`; a new admin route that forgets the role gate fails the role sweep.
If a route is intentionally open to non-admins, add it to `SPECIAL` / `ANY_AUTH_OK` / `PUBLIC` in `tests/test_hardening.py`.

## Known limitations / not done
- **No external penetration test** and no fuzzing beyond the injection/oversize/malformed cases above.
- Body-size limit checks `Content-Length` only. Chunked uploads without it are not capped by the app; enforce a limit at the
  reverse proxy / host too (Render and Cloudflare both do by default).
- Rate-limit counting is check-then-insert, so a simultaneous burst can slightly exceed the limit.
- The static frontend needs its own security headers/CSP at the host (Stage 6: `_headers` for Cloudflare Pages).
- Runtime DB role is still the owner role in development; least-privilege role setup is Stage 6.
- Email delivery through Resend has not been exercised against the real service.
- There is no password-reset or password-change flow yet (not in the approved scope).

## Housekeeping
`python -m scripts.purge_expired` removes sessions expired/revoked > 7 days ago and rate-limit rows > 1 day old.
Schedule it daily (Render cron job or similar). Audit logs and invitations are intentionally kept.
