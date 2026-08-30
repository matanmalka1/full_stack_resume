# Frontend development

The frontend uses the local FastAPI service as its only backend.

For development, configure the backend process with the exact Vite origin:

```text
CV_API_DEV_ORIGIN=http://127.0.0.1:5173
```

Then run `npm run dev` in this directory. Vite listens on `127.0.0.1:5173` with a strict
port and proxies `/api` to `http://127.0.0.1:8765`. It never falls back to another port,
because that would silently disagree with the backend Origin allowlist.

`npm run build` writes the production bundle to `frontend/dist`. `cv web` serves that
bundle and supervises FastAPI plus the Operation worker on one loopback origin.

The Playwright suite uses that production entry point, the real renderer, local object
storage in a temporary project copy, and an explicitly supplied fresh PostgreSQL database.
It refuses a configured AI key, a stale schema, or any pre-existing row in an application
table. From the repository root, a disposable local run is:

```bash
unset OPENAI_API_KEY
export CV_E2E_DB="cv_stage_f_$(date +%Y%m%d%H%M%S)"
docker compose exec -T postgres createdb -U cv "$CV_E2E_DB"
export CV_DATABASE_URL="postgresql+psycopg://cv:cv@127.0.0.1:5433/$CV_E2E_DB"
./.venv/bin/alembic upgrade head
(cd frontend && npm run e2e)
docker compose exec -T postgres dropdb -U cv "$CV_E2E_DB"
unset CV_DATABASE_URL CV_E2E_DB
```

Install both Chromium distributions on a fresh checkout before the run: Node Playwright
drives the UI, while Python Playwright renders the approved CV.

```bash
(cd frontend && npx playwright install chromium)
./.venv/bin/python -m playwright install chromium
```
