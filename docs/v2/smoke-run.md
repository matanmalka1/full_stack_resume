# Deterministic end-to-end smoke run

Proves the deterministic pipeline reaches `ready` on a fresh, isolated Workspace with
no AI key and no money spent. The workflow makes no provider or Internet call, but it
does require the local PostgreSQL service: database access is no longer embedded in the
Workspace.

Everything below runs as **one user, one terminal**, and touches nothing that already
exists: both the Workspace and database have unique smoke-run names, and the existing
Workspace/database are never opened.

## 0. PostgreSQL prerequisite and guard rails

```bash
cd "$(git rev-parse --show-toplevel)"
unset OPENAI_API_KEY
export CV_PROVIDER=deterministic
export CV_SOURCE_ROOT=$(pwd)
export CV_SMOKE_ID=$(date +%Y%m%d%H%M%S)
export CV_SMOKE_WS=/tmp/cv-smoke-$CV_SMOKE_ID
export CV_SMOKE_DB=cv_smoke_$CV_SMOKE_ID
cv_cli() {
  ./.venv/bin/python -m cv_engine.cli "$@"
}

docker compose up -d postgres
docker compose exec -T postgres pg_isready -U cv -d cv
docker compose exec -T postgres createdb -U cv "$CV_SMOKE_DB"
export CV_DATABASE_URL="postgresql+psycopg://cv:cv@127.0.0.1:5433/$CV_SMOKE_DB"

echo "$CV_SMOKE_WS"
echo "$CV_SMOKE_DB"
```

`OPENAI_API_KEY` being unset is the point of the exercise: if any step reaches for a key,
it must fail loudly rather than quietly spend. `pg_isready` must report that the local
Compose service accepts connections before continuing. The commands assume the documented
Compose defaults; when those defaults are overridden, set `CV_DATABASE_URL` to the matching
fresh database instead.

## 1. Create an isolated Workspace

```bash
cv_cli --workspace "$CV_SMOKE_WS" workspace init \
  --purpose test \
  --data-class test \
  --knowledge-from "$CV_SOURCE_ROOT"
```

`--knowledge-from` copies `base/ profiles/ rendering/ config/ ai/` in. Without it the
Workspace has no canonical facts and drafting has nothing to draw on.

`--purpose test --data-class test` marks it non-live, so it can never be confused with
a real Workspace.

```bash
cv_cli --workspace "$CV_SMOKE_WS" workspace upgrade
cv_cli --workspace "$CV_SMOKE_WS" workspace status
```

`workspace upgrade` applies Alembic to the fresh PostgreSQL database. `workspace status`
should then report the five roots under `$CV_SMOKE_WS`, the configured database URL, and
schema revision `0002`.

## 2. Ingest a posting

```bash
cv_cli --workspace "$CV_SMOKE_WS" ingest \
  --company "Smoke Test Ltd" \
  --role "Backend Engineer" \
  --job-text "Backend engineer. Python, FastAPI, PostgreSQL. Build and operate HTTP services."
```

Prints JSON with `application_id` and `job_snapshot_id`. Capture it:

```bash
export CV_SMOKE_APP=$(cv_cli --workspace "$CV_SMOKE_WS" ingest \
  --company "Smoke Test Ltd 2" \
  --role "Backend Engineer" \
  --job-text "Backend engineer. Python, FastAPI, PostgreSQL." \
  | jq -r .application_id)
echo "$CV_SMOKE_APP"
```

## 3. The chain

```bash
cv_cli --workspace "$CV_SMOKE_WS" analyze  "$CV_SMOKE_APP" --provider deterministic
cv_cli --workspace "$CV_SMOKE_WS" draft    "$CV_SMOKE_APP"
cv_cli --workspace "$CV_SMOKE_WS" validate "$CV_SMOKE_APP"
cv_cli --workspace "$CV_SMOKE_WS" approve  "$CV_SMOKE_APP"
cv_cli --workspace "$CV_SMOKE_WS" render   "$CV_SMOKE_APP"
cv_cli --workspace "$CV_SMOKE_WS" ready    "$CV_SMOKE_APP"
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
cv_cli --workspace "$CV_SMOKE_WS" show "$CV_SMOKE_APP"
ls -R "$CV_SMOKE_WS/artifacts"
```

- `show` reports `preparation_state: ready`
- `artifacts/` holds an HTML and a PDF
- `ready` reported no blocking failures
- no step asked for `OPENAI_API_KEY`

## 5. Cleanup

```bash
rm -rf "$CV_SMOKE_WS"
docker compose exec -T postgres dropdb -U cv "$CV_SMOKE_DB"
unset CV_DATABASE_URL CV_SMOKE_APP CV_SMOKE_DB CV_SMOKE_WS CV_SMOKE_ID CV_SOURCE_ROOT
unset -f cv_cli
```

Safe: the Workspace is the unique `/tmp` path printed in section 0 and is marked `test`;
the database is the unique name created in the same section. Neither cleanup target is a
pre-existing development resource.

## Notes

- `propose_selection_plan`, `regenerate_section`, and `regenerate_claim` are
  `always_ai` (`application/operations.py`), meaning they take the AI resource lease
  regardless of the requested provider. None of them has a CLI command, so this
  sequence never reaches one. Do not add them to this run.
- `analyze --provider openai` and `--model` exist but are deliberately not used here.
