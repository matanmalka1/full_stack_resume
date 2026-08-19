# Documentation map

Three kinds of document live here, and the kind decides how it is treated.

| Kind | Where | Rule |
| --- | --- | --- |
| **Specification** — binding on what the product does | `v2/spec/` | Changes only by an approved decision |
| **Record** — what was decided, built, and verified | `v2/records/` | Frozen when its boundary closes; not updated with later state |
| **State** — what is done, what remains, what is blocked | `v2/m2-remaining.md` | The only file that tracks state |

`v2/process/` holds working protocol rather than product content. `v1/` is the legacy
record: evidence, not an active workflow. As of 2026-08-19 it is a frozen archive —
v2 starts with an empty database and there is no migration from v1.
`v1/migration-plan-superseded.md` records the migration that was planned and retired.

## v2 specifications — `v2/spec/`

| File | Owns |
| --- | --- |
| `product-spec.md` | Scope, invariants, non-goals, Definition of Done |
| `state-and-use-cases.md` | Lifecycle, commands, queries, permissions, HTTP mapping |
| `architecture.md` | Layer boundaries, filesystem layout, schema shape, dependency baseline |
| `implementation-plan.md` | Milestones M0–M6, their stages and gates |
| `test-and-acceptance-plan.md` | Test layers, golden matrix, release gates |

## Records — `v2/records/`

| File | Covers |
| --- | --- |
| `architecture-audit.md` | Findings A1–A29 and the M1 boundary work; frozen at M1 close |
| `m1-acceptance.md` | M1 acceptance, its four review rounds, and its evidence |
| `m2-schema-and-repositories.md` | M2 boundary 1 — schema, migrations, repositories |
| `m2-domain-records.md` | M2 boundary 2 — domain records, including Stage 7b |
| `m2-approved-revisions.md` | M2 boundary 2b-i — approved revisions and artifact binding |
| `m2-operations.md` | M2 §4.4 — durable Operations, recovery, and Class C evidence |
| `m2-knowledge-consistency.md` | M2 §4.5 — journaled Knowledge mutation and recovery evidence |
| `stage7-validation-report-options.md` | The option analysis behind the `ValidationReport` decision |

## State and process

- `v2/m2-remaining.md` — M2 state. Scope authority stays with the plan; this file tracks
  only what is done, remaining, or blocked.
- `v2/cleanup-todos.md` — non-milestone cleanup items.
- `v2/process/execution-protocol.md` — how work is split across parallel agents. Adds to
  `CLAUDE.md`; repeats none of it.

## v1 — `v1/`

`upgrade-handoff.md` is the binding description of what v1 did and why. `architecture.md`,
`review.md`, `implementation-plan.md`, `verification.md`, `migration-restore.md`, and
`retrospective-migration-verification.json` are its supporting evidence.
