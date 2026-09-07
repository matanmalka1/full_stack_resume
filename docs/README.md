# Documentation map

## Specifications — `spec/`

Binding on what the product does. Changes by an approved decision.

| File | Owns |
| --- | --- |
| `product-spec.md` | Scope, invariants, non-goals, Definition of Done |
| `state-and-use-cases.md` | Lifecycle, commands, queries, permissions, HTTP mapping |
| `architecture.md` | Layer boundaries, filesystem layout, schema shape, dependency baseline |
| `test-and-acceptance-plan.md` | Test layers, golden matrix, release gates |

## State and process

- [Tailoring behavior change](tailoring-behavior-change.md) — approved tailoring principles
  and remaining design work for development and sales.
- [Acceptance cases](tailoring-acceptance-cases.md) — Connecteam SDR and WeDev Junior
  Fullstack: source mappings, proposed outputs, and editing scenarios.
- [Wording validation design](tailoring-wording-validation.md) — approved acceptance
  decision D1 and evidence/staleness design; storage and command details remain to be completed.
- [Analysis contract extension](tailoring-analysis-contract.md) — proposed only, nothing
  approved: requirement extraction, interpretation, completeness, identity, analysis
  correction, and selection authority ahead of the wording work.
- `m5-remaining.md` — M5 closure status and only the work explicitly carried forward.
- `process/execution-protocol.md` — how work is split across parallel agents.

## Baseline

Persistence is PostgreSQL/SQLAlchemy/Alembic plus a storage-neutral local-or-S3-compatible
object store. Runtime configuration supports one `.env` below the real process
environment; `OPENAI_API_KEY` is environment-only and configured secrets are masked at
reporting boundaries. `spec/architecture.md` owns these contracts.

Closed milestone records and the v1 archive were removed on 2026-08-30; they are in Git
history.
