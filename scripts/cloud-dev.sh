#!/usr/bin/env bash
# Bring up (or tear down) the full local dev stack in one command: local
# PostgreSQL, Alembic migrations, the API, the worker, and the Vite frontend.
#
# Every cloud session is a fresh VM cloned from git, so nothing here can
# assume yesterday's state survived. The script is safe to re-run: each step
# checks what already exists before creating or starting anything.
#
# Usage: ./scripts/cloud-dev.sh [up|down|status]   (default: up)

set -euo pipefail

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

RUN_DIR="$repo_root/logs/dev"
PID_DIR="$RUN_DIR/pids"
PG_USER="cv"
PG_PASSWORD="cv"
PG_DB="cv"
DOCKER_PG_PORT="${CV_POSTGRES_PORT:-5433}"
TEMPLATE_DB_URL="postgresql+psycopg://cv:cv@127.0.0.1:${DOCKER_PG_PORT}/cv"
FRONTEND_HOST="127.0.0.1"
FRONTEND_PORT="5173"

log()  { printf '[cloud-dev] %s\n' "$*"; }
die()  { printf '[cloud-dev] ERROR: %s\n' "$*" >&2; exit 1; }

# --- .env -------------------------------------------------------------

ensure_env_file() {
    if [ ! -f .env ]; then
        cp .env.example .env
        log ".env created from .env.example (git-ignored; never committed)"
    else
        log ".env already exists, leaving it as-is"
    fi
}

# Load .env into this shell so CV_API_HOST/PORT etc. reflect any
# customization, not just the script's own defaults.
load_env() {
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
}

# Adds KEY=VALUE only if KEY is not already set (commented or absent).
# Never overwrites a value the user already made explicit.
ensure_env_default() {
    key="$1"; value="$2"
    grep -qE "^${key}=" .env && return 0
    sed -i "/^# ${key}=/d" .env
    printf '%s=%s\n' "$key" "$value" >> .env
    log "set default ${key} in .env"
}

# Vite's dev proxy forwards the browser's real Origin (changeOrigin: false),
# so without this, every state-changing request from the UI gets a 403.
ensure_dev_origin() {
    ensure_env_default CV_API_DEV_ORIGIN "http://${FRONTEND_HOST}:${FRONTEND_PORT}"
}

# --- PostgreSQL ---------------------------------------------------------

have_docker_postgres() {
    command -v docker >/dev/null 2>&1 || return 1
    docker info >/dev/null 2>&1 || return 1
    docker compose version >/dev/null 2>&1 || return 1
    return 0
}

start_postgres_docker() {
    log "Docker daemon available, using docker-compose postgres"
    docker compose up -d postgres >/dev/null
    wait_for "pg_isready -h 127.0.0.1 -p ${DOCKER_PG_PORT} -U ${PG_USER} -d ${PG_DB} >/dev/null 2>&1" 60 \
        "postgres (docker, port ${DOCKER_PG_PORT})"
    # .env.example's default CV_DATABASE_URL already matches docker-compose's
    # published port, so nothing to rewrite here.
}

as_postgres() {
    if id postgres >/dev/null 2>&1 && command -v su >/dev/null 2>&1; then
        su postgres -c "$1"
    elif command -v sudo >/dev/null 2>&1; then
        sudo -u postgres bash -c "$1"
    else
        die "cannot run as the postgres OS user (no su/sudo available)"
    fi
}

ensure_local_postgres_installed() {
    command -v pg_lsclusters >/dev/null 2>&1 && return 0
    log "postgresql not found locally, attempting apt-get install (best effort)"
    command -v apt-get >/dev/null 2>&1 || die "postgresql is missing and apt-get is unavailable; install PostgreSQL manually or enable Docker"
    apt-get update -qq && apt-get install -y postgresql >/dev/null \
        || die "postgresql is missing and 'apt-get install postgresql' failed; install it manually (or add it to the cloud environment's setup script) or enable Docker"
}

local_cluster_port() {
    pg_lsclusters 2>/dev/null | awk 'NR==2 {print $3}'
}

start_postgres_local() {
    log "Docker not available, using a local PostgreSQL cluster"
    ensure_local_postgres_installed

    if ! pg_lsclusters 2>/dev/null | awk 'NR==2 {print $4}' | grep -q '^online$'; then
        service postgresql start >/dev/null 2>&1 \
            || die "could not start the local postgresql service"
    fi

    port=$(local_cluster_port)
    [ -n "$port" ] || port=5432
    wait_for "pg_isready -h 127.0.0.1 -p ${port} >/dev/null 2>&1" 30 "postgres (local, port ${port})"

    as_postgres "psql -tc \"SELECT 1 FROM pg_roles WHERE rolname='${PG_USER}'\"" | grep -q 1 \
        || as_postgres "psql -c \"CREATE ROLE ${PG_USER} LOGIN PASSWORD '${PG_PASSWORD}';\"" >/dev/null
    as_postgres "psql -tc \"SELECT 1 FROM pg_database WHERE datname='${PG_DB}'\"" | grep -q 1 \
        || as_postgres "createdb -O ${PG_USER} ${PG_DB}"

    local_url="postgresql+psycopg://${PG_USER}:${PG_PASSWORD}@127.0.0.1:${port}/${PG_DB}"
    if [ "$port" != "$DOCKER_PG_PORT" ]; then
        current=$(grep -E '^CV_DATABASE_URL=' .env | cut -d= -f2-)
        if [ "$current" = "$TEMPLATE_DB_URL" ]; then
            sed -i "s#^CV_DATABASE_URL=.*#CV_DATABASE_URL=${local_url}#" .env
            log "pointed CV_DATABASE_URL at the local cluster (port ${port})"
        fi
    fi
}

ensure_postgres() {
    if have_docker_postgres; then
        start_postgres_docker
    else
        start_postgres_local
    fi
}

# --- Python / migrations -------------------------------------------------

ensure_venv() {
    if [ -x .venv/bin/python ]; then
        log ".venv already present, skipping bootstrap"
        return 0
    fi
    command -v uv >/dev/null 2>&1 || die "uv is required; see https://docs.astral.sh/uv/getting-started/installation/"
    uv venv --python "$(command -v python3)" .venv
    uv pip install --python .venv/bin/python -e '.[test]'
    # Playwright's browser download is best-effort: it needs a CDN host that
    # some cloud network policies block, and the API/worker/frontend don't
    # need it. Rendering/browser-test work does; see README for that gate.
    ./.venv/bin/python -m playwright install chromium \
        || log "playwright chromium install failed/skipped (not needed for API/worker/frontend)"
}

run_migrations() {
    log "running alembic upgrade head"
    ./.venv/bin/alembic upgrade head
}

# --- Frontend deps ---------------------------------------------------------

ensure_frontend_deps() {
    if [ -d frontend/node_modules ]; then
        log "frontend/node_modules already present, skipping npm install"
        return 0
    fi
    (cd frontend && npm install)
}

# --- process management -----------------------------------------------

wait_for() {
    check="$1"; timeout="$2"; desc="$3"
    elapsed=0
    until eval "$check"; do
        elapsed=$((elapsed + 1))
        [ "$elapsed" -ge "$timeout" ] && die "timed out waiting for ${desc}"
        sleep 1
    done
    log "${desc} is ready"
}

pid_alive() {
    [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null
}

start_bg() {
    name="$1"; pidfile="$PID_DIR/${name}.pid"; logfile="$RUN_DIR/${name}.out"; shift
    if pid_alive "$pidfile"; then
        log "${name} already running (pid $(cat "$pidfile")), skipping"
        return 0
    fi
    ( set -a; . "$repo_root/.env"; set +a; exec "$@" ) > "$logfile" 2>&1 &
    echo $! > "$pidfile"
    log "started ${name} (pid $(cat "$pidfile")), logging to ${logfile}"
}

start_api() {
    host="${CV_API_HOST:-127.0.0.1}"; port="${CV_API_PORT:-8765}"
    start_bg api ./.venv/bin/python -m uvicorn cv_engine.runtime.asgi:app --host "$host" --port "$port"
}

start_worker() {
    start_bg worker ./.venv/bin/python -m cv_engine.worker
}

start_frontend() {
    ( cd frontend && start_bg frontend npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" )
}

health_check_all() {
    host="${CV_API_HOST:-127.0.0.1}"; port="${CV_API_PORT:-8765}"
    wait_for "curl -sf http://${host}:${port}/api/v1/health >/dev/null" 30 "API (http://${host}:${port})"
    pid_alive "$PID_DIR/worker.pid" || die "worker process is not running, see ${RUN_DIR}/worker.out"
    log "worker is running (pid $(cat "$PID_DIR/worker.pid"))"
    wait_for "curl -sf http://${FRONTEND_HOST}:${FRONTEND_PORT}/ >/dev/null" 30 "frontend (http://${FRONTEND_HOST}:${FRONTEND_PORT})"
}

# --- subcommands -----------------------------------------------------

cmd_up() {
    mkdir -p "$PID_DIR"
    ensure_env_file
    ensure_dev_origin
    load_env
    ensure_postgres
    ensure_venv
    run_migrations
    ensure_frontend_deps
    start_api
    start_worker
    start_frontend
    health_check_all
    log "all services healthy: API http://${CV_API_HOST:-127.0.0.1}:${CV_API_PORT:-8765}, frontend http://${FRONTEND_HOST}:${FRONTEND_PORT}"
    log "logs: ${RUN_DIR}/{api,worker,frontend}.out  (app logs: logs/server.jsonl, logs/operations.jsonl)"
}

cmd_down() {
    for name in api worker frontend; do
        pidfile="$PID_DIR/${name}.pid"
        if pid_alive "$pidfile"; then
            pid=$(cat "$pidfile")
            kill "$pid" 2>/dev/null || true
            for _ in $(seq 1 10); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
            kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
            log "stopped ${name} (pid ${pid})"
        else
            log "${name} not running"
        fi
        rm -f "$pidfile"
    done
    log "PostgreSQL left running (shared local service); nothing else to stop"
}

cmd_status() {
    [ -f .env ] && load_env
    host="${CV_API_HOST:-127.0.0.1}"; port="${CV_API_PORT:-8765}"
    for name in api worker frontend; do
        pidfile="$PID_DIR/${name}.pid"
        if pid_alive "$pidfile"; then
            printf '%-10s up (pid %s)\n' "$name" "$(cat "$pidfile")"
        else
            printf '%-10s down\n' "$name"
        fi
    done
    curl -sf "http://${host}:${port}/api/v1/health" >/dev/null 2>&1 \
        && echo "API health   : ok" || echo "API health   : unreachable"
    curl -sf "http://${FRONTEND_HOST}:${FRONTEND_PORT}/" >/dev/null 2>&1 \
        && echo "frontend     : ok" || echo "frontend     : unreachable"
}

case "${1:-up}" in
    up)     cmd_up ;;
    down)   cmd_down ;;
    status) cmd_status ;;
    *)      die "usage: $0 [up|down|status]" ;;
esac
