#!/bin/sh
# SessionStart entry point for cloud agent containers. When the environment's
# setup script already provisioned the container (.venv and frontend deps
# present), only start PostgreSQL; otherwise run the full provisioning.

set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

if [ -x .venv/bin/python ] && [ -d frontend/node_modules ] && [ -e .env ]; then
    exec ./scripts/cloud-db.sh
fi
exec ./scripts/cloud-setup.sh
