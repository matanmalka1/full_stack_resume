#!/bin/sh

set -u

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

python="$repo_root/.venv/bin/python"

mobile=false
case "$#:${1-}" in
    0:) ;;
    1:--mobile) mobile=true ;;
    *)
        echo "usage: ./scripts/dev.sh [--mobile]" >&2
        exit 2
        ;;
esac

if [ ! -x "$python" ]; then
    echo "development environment is missing; run ./scripts/bootstrap-worktree.sh first" >&2
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    echo "npm is required to run the frontend" >&2
    exit 1
fi

if [ ! -d "$repo_root/frontend/node_modules" ]; then
    echo "frontend dependencies are missing; run: cd frontend && npm install" >&2
    exit 1
fi

frontend_command=dev
web_url=http://localhost:5173

if [ "$mobile" = true ]; then
    mobile_host=${CV_DEV_MOBILE_HOST-}
    if [ -z "$mobile_host" ]; then
        mobile_host=$(
            "$python" -c '
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    sock.connect(("192.0.2.1", 80))
    print(sock.getsockname()[0])
finally:
    sock.close()
' 2>/dev/null
        ) || true
    fi

    if ! "$python" -c '
import ipaddress
import sys

address = ipaddress.ip_address(sys.argv[1])
if address.version != 4 or address.is_loopback or address.is_unspecified:
    raise SystemExit(1)
' "$mobile_host" 2>/dev/null; then
        echo "could not detect a usable LAN IPv4 address; set CV_DEV_MOBILE_HOST explicitly" >&2
        exit 1
    fi

    frontend_command=dev:mobile
    web_url="http://$mobile_host:5173"
fi

export CV_API_DEV_ORIGIN=$web_url

api_pid=
worker_pid=
frontend_pid=
started_pid=
cleaned_up=false

start_in_process_group() {
    "$python" -c '
import os
import sys

os.setsid()
os.execvp(sys.argv[1], sys.argv[1:])
' "$@" &
    started_pid=$!
}

process_group_exists() {
    kill -0 -- "-$1" 2>/dev/null
}

signal_process_group() {
    signal=$1
    pid=$2

    # The launcher calls setsid(), making its PID the process-group ID. If
    # shutdown races with setsid(), signal the direct child as a fallback.
    kill "-$signal" -- "-$pid" 2>/dev/null || \
        kill "-$signal" "$pid" 2>/dev/null || true
}

cleanup() {
    if [ "$cleaned_up" = true ]; then
        return
    fi
    cleaned_up=true

    trap - EXIT INT TERM
    for pid in "$api_pid" "$worker_pid" "$frontend_pid"; do
        if [ -n "$pid" ]; then
            signal_process_group TERM "$pid"
        fi
    done

    attempts=0
    while [ "$attempts" -lt 5 ]; do
        groups_running=false
        for pid in "$api_pid" "$worker_pid" "$frontend_pid"; do
            if [ -n "$pid" ] && process_group_exists "$pid"; then
                groups_running=true
                break
            fi
        done

        if [ "$groups_running" = false ]; then
            break
        fi

        sleep 1
        attempts=$((attempts + 1))
    done

    for pid in "$api_pid" "$worker_pid" "$frontend_pid"; do
        if [ -n "$pid" ] && process_group_exists "$pid"; then
            echo "process group $pid did not stop gracefully; killing it" >&2
            signal_process_group KILL "$pid"
        fi
    done

    for pid in "$api_pid" "$worker_pid" "$frontend_pid"; do
        if [ -n "$pid" ]; then
            wait "$pid" 2>/dev/null || true
        fi
    done
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

start_in_process_group "$python" -m uvicorn cv_engine.runtime.asgi:app \
    --host 127.0.0.1 \
    --port 8765 \
    --reload
api_pid=$started_pid

start_in_process_group "$python" -m cv_engine.worker
worker_pid=$started_pid

start_in_process_group sh -c 'cd "$1" && exec npm run "$2"' sh "$repo_root/frontend" "$frontend_command"
frontend_pid=$started_pid

echo "Development services started:"
echo "  Web UI: $web_url"
echo "  API:    http://127.0.0.1:8765"
echo "Press Ctrl+C to stop all services."

while :; do
    for service_and_pid in \
        "API:$api_pid" \
        "worker:$worker_pid" \
        "frontend:$frontend_pid"
    do
        service=${service_and_pid%%:*}
        pid=${service_and_pid#*:}

        if ! kill -0 "$pid" 2>/dev/null; then
            if wait "$pid"; then
                status=0
            else
                status=$?
            fi
            echo "$service stopped (exit status $status); stopping all services." >&2
            exit "$status"
        fi
    done
    sleep 1
done
