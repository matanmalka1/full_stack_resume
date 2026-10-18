# Project Agent Instructions

A CV tailoring tool: FastAPI backend, React frontend, PostgreSQL, a separate worker
for AI Operations. Multi-user; each user reaches only their own data.

## Running

- API: `uvicorn cv_engine.runtime.asgi:app` — serves HTTP, queues Operations.
- Worker: `python -m cv_engine.worker` — executes Operations.
- Frontend: `cd frontend && npm run dev`.
- Setup and the rest: `README.md`.

## Tests

Run the tests yourself and report the commands with their real output. In a cloud
container (`CLAUDE_CODE_REMOTE=true`), run `./scripts/cloud-db.sh` first.

- Run the focused tests for what the diff touched, not the whole suite.
- Backend: `./.venv/bin/python -m pytest -q <paths>`.
- Frontend: `npm --prefix frontend run check` (typecheck, lint, unit tests).
- Schema change (`alembic/`): also run `tests/platform/test_schema.py` and an
  upgrade of an empty database.
- Rendering change: also run the golden tests (`tests/e2e/test_golden.py`) and the
  relevant browser tests. Golden hashes move only when the output was meant to change.
- Never report a failing test as passing or as a warning.

## Hard rules

- **User isolation.** Every query and command is scoped to the signed-in user. A record
  reachable by another user is a bug of the highest severity.
- **Don't destroy history.** Submissions, their files, and the AI call log are records
  of what happened. Don't rewrite or delete them.
- **React talks to the backend only through the FastAPI API.** Logic lives in the
  application layer, not in routers.
- **Cloud work** lands on its own branch and reaches `main` through a pull request.

## Working with the docs

`docs/` describes the current design. It is a description, not a law: when it is
wrong, outdated, or gets in the way of what the user asks, say so and propose a change
instead of defending it. Judge a design by the code and by what the user wants from
the product.
