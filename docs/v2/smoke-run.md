# Offline end-to-end smoke run

Proves the deterministic pipeline reaches `ready` on a fresh, isolated Workspace with
no AI key and no money spent. Run before any Postgres / auth / storage work, so that
later failures have a known-good baseline to be compared against.

Everything below runs as **one user, one terminal**, and touches nothing that already
exists: the Workspace lives in `/tmp`, and the existing `data/` is never opened.

## 0. Guard rails

```bash
cd /Users/matanmalka/Projects/resume_python
unset OPENAI_API_KEY
export CV_PROVIDER=deterministic
export WS=/tmp/cv-smoke-$(date +%Y%m%d-%H%M%S)
echo "$WS"
```

`unset` is the point of the exercise: if any step reaches for a key, it must fail
loudly rather than quietly spend.

## 1. Create an isolated Workspace

```bash
cv --workspace "$WS" workspace init \
  --purpose test \
  --data-class test \
  --knowledge-from /Users/matanmalka/Projects/resume_python
```

`--knowledge-from` copies `base/ profiles/ rendering/ config/ ai/` in. Without it the
Workspace has no canonical facts and drafting has nothing to draw on.

`--purpose test --data-class test` marks it non-live, so it can never be confused with
a real Workspace.

```bash
cv --workspace "$WS" workspace status
cv --workspace "$WS" init
```

`workspace status` should report the five roots under `$WS`. `init` creates the SQLite
schema.

## 2. Ingest a posting

```bash
cv --workspace "$WS" ingest \
  --company "Smoke Test Ltd" \
  --role "Backend Engineer" \
  --job-text "Backend engineer. Python, FastAPI, PostgreSQL. Build and operate HTTP services."
```

Prints JSON with `application_id` and `job_snapshot_id`. Capture it:

```bash
export APP=$(cv --workspace "$WS" ingest \
  --company "Smoke Test Ltd 2" \
  --role "Backend Engineer" \
  --job-text "Backend engineer. Python, FastAPI, PostgreSQL." \
  | jq -r .application_id)
echo "$APP"
```

## 3. The chain

```bash
cv --workspace "$WS" analyze  "$APP" --provider deterministic
cv --workspace "$WS" draft    "$APP"
cv --workspace "$WS" validate "$APP"
cv --workspace "$WS" approve  "$APP"
cv --workspace "$WS" render   "$APP"
cv --workspace "$WS" ready    "$APP"
```

Run them **one at a time** and read each JSON before the next. The first non-zero exit
is the finding — do not push past it.

`render` starts Playwright/Chromium and is the slowest step. If Chromium is not
installed:

```bash
python -m playwright install chromium
```

## 4. What a pass looks like

```bash
cv --workspace "$WS" show "$APP"
ls -R "$WS/artifacts"
```

- `show` reports `preparation_state: ready`
- `artifacts/` holds an HTML and a PDF
- `ready` reported no blocking failures
- no step asked for `OPENAI_API_KEY`

## 5. Cleanup

```bash
rm -rf "$WS"
```

Safe: it is a `/tmp` Workspace marked `test`, and nothing else points into it.

## Notes

- `propose_selection_plan`, `regenerate_section`, and `regenerate_claim` are
  `always_ai` (`application/operations.py`), meaning they take the AI resource lease
  regardless of the requested provider. None of them has a CLI command, so this
  sequence never reaches one. Do not add them to this run.
- `analyze --provider openai` and `--model` exist but are deliberately not used here.
