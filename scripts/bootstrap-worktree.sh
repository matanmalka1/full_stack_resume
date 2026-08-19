#!/bin/sh

set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required; install it from https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

if [ -e .venv ]; then
    echo "refusing to replace existing worktree environment: $repo_root/.venv" >&2
    exit 1
fi

if [ "${PLAYWRIGHT_BROWSERS_PATH-}" = "0" ]; then
    echo "PLAYWRIGHT_BROWSERS_PATH=0 would duplicate Chromium inside this worktree" >&2
    exit 1
fi

bootstrap_python=${CV_BOOTSTRAP_PYTHON:-$(command -v python3)}
uv venv --python "$bootstrap_python" .venv
uv pip install --python .venv/bin/python -e '.[test]'
./.venv/bin/python -m playwright install chromium

echo "worktree environment ready: $repo_root/.venv"
