#!/usr/bin/env bash
# Resets a TEST database, starts the API, runs the React smoke tests, stops the API.
# Needs a local PostgreSQL. Usage: TEST_DATABASE_URL=postgresql://user:pass@localhost/dbname ./run_smoke_test.sh
set -e
export DATABASE_URL="${TEST_DATABASE_URL:-postgresql://sp:sp@localhost/sp_test}" CORS_ORIGINS='*' DISABLE_RATE_LIMITS=1
cd "$(dirname "$0")/backend"
python3 - <<PY
import os, psycopg
with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as c:
    c.execute("drop schema public cascade; create schema public;")
PY
python3 -m flask --app app init-db
python3 -m flask --app app create-admin --email admin@demo.test --name "Asha Admin" --password 'Admin@1234' >/dev/null
python3 -m flask --app app demo-data
python3 app.py </dev/null >/tmp/upstep_api.log 2>&1 &
API=$!; trap 'kill $API 2>/dev/null' EXIT
sleep 4
# (the React tests create the applicant they need themselves)
cd ../frontend && VITE_API_URL=http://localhost:5000 npx vitest run
