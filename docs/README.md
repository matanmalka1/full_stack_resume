# Documentation map

## Specifications — `spec/`

Binding on what the product does. Changes by an approved decision.

| File | Owns |
| --- | --- |
| `product-spec.md` | Scope, invariants, non-goals, Definition of Done |
| `state-and-use-cases.md` | Lifecycle, commands, queries, permissions, HTTP mapping |
| `architecture.md` | Layer boundaries, filesystem layout, schema shape, dependency baseline |
| `test-and-acceptance-plan.md` | Test layers, golden matrix, release gates |

## Decisions, acceptance, and active work

- [Tailoring behavior change](tailoring-behavior-change.md) — approved decisions D1–D4
  and the three-delivery roadmap. Delivery 1 is implemented with explicitly recorded
  acceptance gaps; deliveries 2–3 remain future work.
- [Acceptance cases](tailoring-acceptance-cases.md) — Connecteam SDR and WeDev Junior
  Fullstack: source mappings, proposed outputs, and editing scenarios.
- [Wording validation design](tailoring-wording-validation.md) — approved acceptance
  decision D1 and evidence/staleness design. It is the active design record for the
  unimplemented seventh AI task, `assess_claim_support`, and its storage/command/UI flow.
- [Delivery 1 status](tailoring-stage-1-plan.md) — what landed for correct job analysis,
  the evidence reported at delivery time, and the remaining acceptance/configuration gaps.
- [Execution protocol](process/execution-protocol.md) — optional coordination rules for
  work that can be split safely across isolated worktrees.

Closed milestone plans and superseded analysis-design drafts are retained in Git history,
not in the active documentation tree.

## Baseline

Persistence is PostgreSQL/SQLAlchemy/Alembic plus a storage-neutral local-or-S3-compatible
object store. Runtime configuration supports one `.env` below the real process
environment; `OPENAI_API_KEY` is environment-only and configured secrets are masked at
reporting boundaries. `spec/architecture.md` owns these contracts.

Closed milestone records and the v1 archive were removed on 2026-08-30; they are in Git
history.
