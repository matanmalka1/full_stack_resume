#!/bin/sh
# Start the local PostgreSQL of a cloud agent container and bring the runtime and
# test databases to Alembic head. Idempotent: safe at every session start.
#
# Cloud containers do not keep background processes between the setup phase and
# the task, so this runs again whenever a session begins.

set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

db_user=cv
db_password=cv
db_port=${CV_CLOUD_POSTGRES_PORT:-5432}

as_postgres() {
    if [ "$(id -u)" = 0 ]; then
        su postgres -c "$*"
    else
        sudo -u postgres sh -c "$*"
    fi
}

if ! pg_isready -q -h 127.0.0.1 -p "$db_port" 2>/dev/null; then
    service postgresql start >/dev/null 2>&1 || sudo service postgresql start
    i=0
    until pg_isready -q -h 127.0.0.1 -p "$db_port"; do
        i=$((i + 1))
        if [ "$i" -ge 30 ]; then
            echo "postgresql did not become ready on port $db_port" >&2
            exit 1
        fi
        sleep 1
    done
fi

as_postgres "psql -p $db_port -tAc \"SELECT 1 FROM pg_roles WHERE rolname = '$db_user'\"" | grep -q 1 \
    || as_postgres "psql -p $db_port -c \"CREATE ROLE $db_user LOGIN CREATEDB PASSWORD '$db_password'\""

for db in cv cv_test; do
    as_postgres "psql -p $db_port -tAc \"SELECT 1 FROM pg_database WHERE datname = '$db'\"" | grep -q 1 \
        || as_postgres "createdb -p $db_port -O $db_user $db"
    CV_DATABASE_URL="postgresql+psycopg://$db_user:$db_password@127.0.0.1:$db_port/$db" \
        ./.venv/bin/alembic upgrade head >/dev/null
done

echo "postgresql ready on 127.0.0.1:$db_port (cv, cv_test at head)"
