# Project Agent Instructions

These instructions govern how coding agents work in this repository.

## Authority

Before any repository task, read `docs/v1-upgrade-handoff.md` completely. For v2 work,
also read the six approved v2 documents relevant to the task; before a new milestone or
cross-cutting change, read all six:

- `docs/v2-product-spec.md`
- `docs/v2-architecture.md`
- `docs/v2-state-and-use-cases.md`
- `docs/v2-implementation-plan.md`
- `docs/v2-test-and-acceptance-plan.md`
- `docs/v2-migration-plan.md`

Authority order for v2:

1. `docs/v2-product-spec.md` — binding v2 product scope and invariants.
2. `docs/v2-state-and-use-cases.md` — binding lifecycle, command, query, and permission
   contracts.
3. `docs/v2-architecture.md` — binding architecture boundaries.
4. The v2 implementation, test/acceptance, and migration plans for their respective
   concerns.
5. `docs/v1-upgrade-handoff.md` — binding inherited factual, validation, historical,
   and migration-safety baseline except where the approved v2 documents explicitly
   change v1 product behavior.
6. `AGENTS.md` / `CLAUDE.md` — repository working rules.
7. `README.md` — human-facing setup and usage documentation.
8. Existing code, configuration, and legacy documentation — current-state evidence.

If approved v2 documents conflict with inherited v1 behavior, stop unless the v2 change
is explicit. Do not silently reinterpret a conflict. The pre-v1 generation workflow is
retired; historical sources and artifacts are evidence only, not an active tailoring
workflow.

## Product decisions and autonomy

- Internal implementation details may change when observable behavior, safety, and
  product semantics remain unchanged.
- Do not silently change workflow, validation behavior, fact semantics, application
  statuses, migration behavior, artifact lifecycle, or other product decisions.
- Proceed by default. Stop only for a blocker, unresolved specification conflict,
  required semantic deviation, material data-loss risk, or migration-safety failure.
- Explain the issue and consequences before requesting a user decision.

## Facts and AI boundaries

- Never invent, strengthen, merge, or "improve" candidate facts.
- One fact has one canonical location. Profiles may reference it; they may not create
  conflicting copies.
- New facts follow `pending -> confirmed -> canonical` unless explicitly confirmed by
  the user in the same message.
- Unsupported factual claims must block approval and `ready_qualified`, including in
  fast mode.
- AI proposes classification, selection, and wording. Canonical facts and deterministic
  validation remain authoritative.
- Preserve canonical historical job titles, dates, metrics, uncertainty, and source
  provenance.

## Historical artifacts and migration safety

- Historical and submitted CV, HTML, PDF, job snapshots, and application artifacts are
  immutable. Never overwrite them.
- Do not migrate live data until a complete snapshot has been created and verified,
  restore instructions exist, migration tests pass, and every historical record and
  artifact is accounted for.
- Test migration against a copy or snapshot before live migration.
- If any migration safety check fails, stop. Do not partially continue or guess.
- Preserve historical data and output meaning, not the legacy architecture.

## Scope discipline

- Implement only the approved v2.0 scope and respect every non-goal in
  `docs/v2-product-spec.md`.
- The local FastAPI + React Web UI is authorized in this v2 worktree. Cloud deployment,
  authentication, PostgreSQL, multi-candidate support, broad multi-provider support,
  and other v2 non-goals are not authorized.
- Keep the CLI first-class. It calls the application layer directly, does not require
  FastAPI, and the deterministic workflow must reach Ready without an AI key.
- Do not begin Dashboard/tracking UI implementation before the mandatory Web/API
  vertical slice reaches Ready with its central failure paths passing.
- Do not perform unrelated refactors or cleanup.
- Do not edit generated HTML by hand; fix the source, template, renderer, or rules.

## Dependencies

- The approved dependency baseline is defined in `docs/v2-architecture.md` section 2.
- Add a dependency only when it enforces contracts, reduces rendering risk, or provides
  a concrete portability or maintainability benefit within v2.0.
- Do not introduce frameworks or infrastructure outside that baseline without a
  demonstrated v2.0 need and a corresponding contract/test update.

## Testing and completion

- Test material changes in proportion to the affected layer.
- Run unit and integration tests, plus relevant golden, rendering, ATS/PDF, API,
  frontend, migration, concurrency, recovery, and regression tests.
- Add a targeted regression test for every material bug discovered during the work.
- Do not claim completion with "implemented" alone.
- Preserve every applicable v1 acceptance invariant and run the relevant gates in
  `docs/v2-test-and-acceptance-plan.md`; report what passed, what failed, and what
  remains.
- A warning may be reported and accepted only where the specification permits it. Hard
  failures block `ready_qualified`, `PreparationState=ready`, and completion.

## Change management

- Keep changes scoped to the active implementation stage.
- Perform v2 work only in the dedicated v2 branch/worktree and an explicitly marked,
  isolated v2 Workspace. Never point development or rehearsal commands at live v1
  data.
- Preserve unrelated user changes in a dirty worktree.
- When implementation work is authorized, create small, intentional commits at stable
  stage boundaries. Do not mix unrelated changes in one commit.
- Never use destructive Git or filesystem operations to simplify migration or cleanup.

## Implementation sequence

Use the mandated sequence:

`Review -> Architecture -> Plan -> Implement -> Test -> Migrate -> Verify`

No approval pause is required between Review and Implementation when there is no stop
condition and the architecture follows the approved v2 specification. Follow M0-M6
gates in `docs/v2-implementation-plan.md`; live cutover remains a separate,
user-authorized event after Release Ready.
