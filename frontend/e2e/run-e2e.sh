#!/usr/bin/env bash
# Full-stack E2E runner. Requires PostgreSQL with an empty database the app role owns (default: manpower_e2e).
# It RESETS that database, bootstraps an Admin, starts the API, runs the UI tests, then stops the API.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"; FRONTEND="$ROOT/frontend"
PORT="${E2E_API_PORT:-8001}"
export DATABASE_URL="${E2E_DATABASE_URL:-postgresql+psycopg://manpower:devpassword@localhost:5432/manpower_e2e}"
export APP_ENV=development SECRET_KEY="e2e-only-secret-key-not-for-real-use-0123456789"
export CORS_ORIGINS="http://localhost:5173" FRONTEND_BASE_URL="http://localhost:5173" EMAIL_PROVIDER=dev_outbox
export E2E_ADMIN_PASSWORD="E2eAdminPassw0rd1"
cd "$BACKEND"; source .venv/bin/activate
rm -rf .dev_outbox
alembic downgrade base >/dev/null 2>&1 || true
alembic upgrade head >/dev/null
printf 'E2E Admin\nadmin@e2e.example.com\n9000000001\n' | BOOTSTRAP_ADMIN_PASSWORD="$E2E_ADMIN_PASSWORD" python -m scripts.bootstrap_admin >/dev/null
python -m uvicorn app.main:app --port "$PORT" --log-level warning >/tmp/e2e-api.log 2>&1 &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT
for i in $(seq 1 30); do curl -sf "localhost:$PORT/api/v1/health/ready" >/dev/null && break; sleep 0.5; done
curl -sf "localhost:$PORT/api/v1/health/ready" >/dev/null || { echo "API did not become ready"; cat /tmp/e2e-api.log; exit 1; }
cd "$FRONTEND"
VITE_API_BASE_URL="http://localhost:$PORT/api/v1" E2E_OUTBOX="$BACKEND/.dev_outbox" npx vitest run -c vitest.e2e.config.js "$@"
