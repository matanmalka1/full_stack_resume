# Project Agent Instructions

These instructions govern how coding agents work in this repository.

## Authority

Before any repository task, read `docs/v1-upgrade-handoff.md` completely.

Authority order for v1:

1. `docs/v1-upgrade-handoff.md` — binding product and implementation specification.
2. `AGENTS.md` / `CLAUDE.md` — repository working rules.
3. `README.md` — human-facing setup and usage documentation.
4. Legacy code, configuration, and documentation — current-state evidence only.

If the v1 handoff conflicts with the README, this file, the legacy Development-only
workflow, or existing code, the handoff wins. Do not silently reinterpret a conflict.

The pre-v1 generation workflow has been retired. Historical sources and artifacts are
evidence only and must not be used as an active tailoring workflow.

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
- Unsupported factual claims must block approval and `ready`, including in fast mode.
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

- Implement only the v1 scope defined in the handoff.
- Do not add the deferred Web UI, PostgreSQL, advanced analytics, broad multi-provider
  support, or other out-of-v1 features.
- Keep the CLI first-class: the complete v1 Definition of Done must work without a Web
  UI.
- Do not perform unrelated refactors or cleanup.
- Do not edit generated HTML by hand; fix the source, template, renderer, or rules.

## Dependencies

- Pydantic, Jinja2, Playwright, and standard-library `sqlite3` are the approved v1
  baseline.
- Add a dependency only when it enforces contracts, reduces rendering risk, or provides
  a concrete portability or maintainability benefit.
- Do not introduce frameworks or infrastructure without a demonstrated v1 need.

## Testing and completion

- Test material changes in proportion to the affected layer.
- Run unit and integration tests, plus relevant golden, rendering, ATS/PDF, migration,
  and regression tests.
- Add a targeted regression test for every material bug discovered during the work.
- Do not claim completion with "implemented" alone.
- Run the acceptance checklist in `docs/v1-upgrade-handoff.md` and report evidence:
  what passed, what failed, and what remains.
- A warning may be reported and accepted only where the specification permits it. Hard
  failures block `ready` and completion.

## Change management

- Keep changes scoped to the active implementation stage.
- Preserve unrelated user changes in a dirty worktree.
- When implementation work is authorized, create small, intentional commits at stable
  stage boundaries. Do not mix unrelated changes in one commit.
- Never use destructive Git or filesystem operations to simplify migration or cleanup.

## Implementation sequence

Use the mandated sequence:

`Review -> Architecture -> Plan -> Implement -> Test -> Migrate -> Verify`

No approval pause is required between Review and Implementation when there is no stop
condition and the architecture follows the binding specification.
