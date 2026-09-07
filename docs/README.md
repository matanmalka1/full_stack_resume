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
- [Analysis contract extension](tailoring-analysis-contract.md) — D2–D4 are closed and
  incorporated into the binding specifications: primary AI requirement extraction,
  the explicit deterministic path, and material professional choices. Remaining
  evidence-matching and selection/budget proposals are not blanket-approved.
- [Stage 1 implementation plan](tailoring-stage-1-plan.md) — job understanding before
  wording; structural decisions are resolved, while threshold/member contracts,
  evidence/boundary mapping, and interpretation enforcement remain to be completed.
  This supporting plan does not override `spec/` or claim runtime implementation.
- `m5-remaining.md` — M5 closure status and only the work explicitly carried forward.
- `process/execution-protocol.md` — how work is split across parallel agents.

## Baseline

Persistence is PostgreSQL/SQLAlchemy/Alembic plus a storage-neutral local-or-S3-compatible
object store. Runtime configuration supports one `.env` below the real process
environment; `OPENAI_API_KEY` is environment-only and configured secrets are masked at
reporting boundaries. `spec/architecture.md` owns these contracts.

Closed milestone records and the v1 archive were removed on 2026-08-30; they are in Git
history.
