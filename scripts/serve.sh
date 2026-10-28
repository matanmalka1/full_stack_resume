#!/usr/bin/env bash
# Production entrypoint for one container: migrate, then run the Operation worker
# and the API side by side. If either exits, the other is stopped and the container
# exits, so the platform restarts both together.
#
# Expects CV_DATABASE_URL, or a plain postgresql:// DATABASE_URL as hosting
# platforms provide it, and PORT for the API.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ -z "${CV_DATABASE_URL:-}" ] && [ -n "${DATABASE_URL:-}" ]; then
    export CV_DATABASE_URL="postgresql+psycopg://${DATABASE_URL#*://}"
fi

alembic upgrade head

# A zero-downtime deploy starts this container while the previous one still holds
# the single-worker lock, so a refused (or crashed) worker is retried rather than
# taking the API down with it. Only a clean exit, after a stop signal, ends the loop.
run_worker() {
    local child
    trap 'kill -TERM "$child" 2>/dev/null || true; wait "$child" || true; exit 0' TERM INT
    while true; do
        python -m cv_engine.worker &
        child=$!
        wait "$child" && return 0
        sleep 5
    done
}

run_worker &
worker_pid=$!
uvicorn cv_engine.runtime.asgi:app --host 0.0.0.0 --port "${PORT:-8765}" &
api_pid=$!

trap 'kill -TERM "$worker_pid" "$api_pid" 2>/dev/null || true' TERM INT
status=0
wait -n || status=$?
kill -TERM "$worker_pid" "$api_pid" 2>/dev/null || true
wait || true
exit "$status"
