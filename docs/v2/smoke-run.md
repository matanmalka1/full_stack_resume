# Deterministic end-to-end smoke run

Proves the deterministic pipeline reaches `ready` against a fresh database with no AI
key and no money spent. The workflow makes no provider or Internet call.

Everything below runs as **one user, one terminal** from the project root. The database
has a unique smoke-run name.

## 0. PostgreSQL prerequisite and guard rails

```bash
cd "$(git rev-parse --show-toplevel)"
unset OPENAI_API_KEY
export CV_PROVIDER=deterministic
export CV_SMOKE_ID=$(date +%Y%m%d%H%M%S)
export CV_SMOKE_DB=cv_smoke_$CV_SMOKE_ID
cv_cli() {
  ./.venv/bin/python -m cv_engine.cli "$@"
}

docker compose up -d postgres
docker compose exec -T postgres pg_isready -U cv -d cv
docker compose exec -T postgres createdb -U cv "$CV_SMOKE_DB"
export CV_DATABASE_URL="postgresql+psycopg://cv:cv@127.0.0.1:5433/$CV_SMOKE_DB"

echo "$CV_SMOKE_DB"
```

`OPENAI_API_KEY` being unset is the point of the exercise. It is environment-only, so a
project `.env` cannot re-enable AI after this `unset`. If any step reaches
for a key, it must fail loudly rather than quietly spend. `pg_isready` must report that the
local Compose service accepts connections before continuing. The commands assume the
documented Compose defaults; when those defaults are overridden, set `CV_DATABASE_URL` to
the matching fresh database instead.

## 1. Upgrade the fresh database

```bash
./.venv/bin/alembic upgrade head
```

Alembic upgrades the fresh PostgreSQL database directly.

## 2. Ingest a posting

```bash
cv_cli ingest \
  --company "Smoke Test Ltd" \
  --role "Backend Engineer" \
  --job-text "Backend engineer. Python, FastAPI, PostgreSQL. Build and operate HTTP services."
```

Prints JSON with `application_id` and `job_snapshot_id`. Capture it:

```bash
export CV_SMOKE_APP=$(cv_cli ingest \
  --company "Smoke Test Ltd 2" \
  --role "Backend Engineer" \
  --job-text "Backend engineer. Python, FastAPI, PostgreSQL." \
  | jq -r .application_id)
echo "$CV_SMOKE_APP"
```

## 3. The chain

```bash
cv_cli analyze  "$CV_SMOKE_APP" --provider deterministic
cv_cli draft    "$CV_SMOKE_APP"
cv_cli validate "$CV_SMOKE_APP"
cv_cli approve  "$CV_SMOKE_APP"
cv_cli render   "$CV_SMOKE_APP"
cv_cli ready    "$CV_SMOKE_APP"
```

Run them **one at a time** and read each JSON before the next. The first non-zero exit
is the finding — do not push past it.

`render` starts Playwright/Chromium and is the slowest step. If Chromium is not
installed:

```bash
./.venv/bin/python -m playwright install chromium
```

## 4. What a pass looks like

```bash
cv_cli show "$CV_SMOKE_APP"
ls -R artifacts
```

- `show` reports `preparation_state: ready`
- `artifacts/` holds an HTML and a PDF
- `ready` reported no blocking failures
- no step asked for `OPENAI_API_KEY`

## 5. Cleanup

```bash
docker compose exec -T postgres dropdb -U cv "$CV_SMOKE_DB"
unset CV_DATABASE_URL CV_SMOKE_APP CV_SMOKE_DB CV_SMOKE_ID
unset -f cv_cli
```

The database is the unique name created in section 0. Local generated artifacts are
regenerable and are not deleted automatically by this guide.

## Notes

- `propose_selection_plan`, `regenerate_section`, and `regenerate_claim` are
  `always_ai` (`application/operations.py`), meaning they take the AI resource lease
  regardless of the requested provider. None of them has a CLI command, so this
  sequence never reaches one. Do not add them to this run.
- `analyze --provider openai` and `--model` exist but are deliberately not used here.
