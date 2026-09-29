#!/bin/sh
# Provision a cloud agent container (Claude Code on the web, Codex cloud):
# Python venv, frontend deps, Chromium, local PostgreSQL. Idempotent - a
# cached container skips what is already installed.
#
# For local machines, follow the Setup instructions in README.md.

set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

apt_install() {
    if [ "$(id -u)" = 0 ]; then
        apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@"
    else
        sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@"
    fi
}

if ! command -v pg_ctlcluster >/dev/null 2>&1; then
    apt_install postgresql postgresql-contrib
fi

if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    PATH="$HOME/.local/bin:$PATH"
    export PATH
fi

if [ ! -x .venv/bin/python ]; then
    uv venv --python 3.12 .venv
fi
uv pip install --python .venv/bin/python -q -e '.[test]'
./.venv/bin/python -m playwright install --with-deps chromium

if [ ! -d frontend/node_modules ]; then
    npm ci --prefix frontend
fi

if [ ! -e .env ]; then
    sed "s#^CV_DATABASE_URL=.*#CV_DATABASE_URL=postgresql+psycopg://cv:cv@127.0.0.1:${CV_CLOUD_POSTGRES_PORT:-5432}/cv#" \
        .env.example > .env
fi

./scripts/cloud-db.sh

echo "cloud environment ready: $repo_root"
