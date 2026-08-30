# Documentation map

## Specifications — `spec/`

Binding on what the product does. Changes by an approved decision.

| File | Owns |
| --- | --- |
| `product-spec.md` | Scope, invariants, non-goals, Definition of Done |
| `state-and-use-cases.md` | Lifecycle, commands, queries, permissions, HTTP mapping |
| `architecture.md` | Layer boundaries, filesystem layout, schema shape, dependency baseline |
| `implementation-plan.md` | Milestones and their gates |
| `test-and-acceptance-plan.md` | Test layers, golden matrix, release gates |

## State and process

- `m4-remaining.md` — what is done, what remains, what is blocked.
- `cleanup-todos.md` — non-milestone cleanup items.
- `smoke-run.md` — deterministic no-AI CLI run against a fresh PostgreSQL database.
- `process/execution-protocol.md` — how work is split across parallel agents.

## Baseline

Persistence is PostgreSQL/SQLAlchemy/Alembic plus a storage-neutral local-or-S3-compatible
object store. Runtime configuration supports one `.env` below the real process
environment; `OPENAI_API_KEY` is environment-only and configured secrets are masked at
reporting boundaries. `spec/architecture.md` owns these contracts.

Closed milestone records and the v1 archive were removed on 2026-08-30; they are in Git
history.
