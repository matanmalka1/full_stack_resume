# v1 Implementation Plan

The binding sequence is `Review -> Architecture -> Plan -> Implement -> Test ->
Migrate -> Verify`.

## Completed before implementation

- [x] Read the binding handoff and repository rules completely.
- [x] Review code, configuration, tracking rows, artifacts, baseline validators, Git
  state, and runtime dependencies.
- [x] Record migration anomalies and deterministic legacy-status interpretation.
- [x] Define the v1 architecture and safety boundaries.

## Implement

- [ ] Add dependency metadata and the Pydantic domain contracts.
- [ ] Add fact/profile/rule loaders and duplicate/fact-lifecycle enforcement.
- [ ] Add deterministic classification, fit/gap analysis, fact selection, drafting,
  exact claim linkage, overrides, and the provider task boundary.
- [ ] Add SQLite schema/repositories, immutable history, status transitions, actions,
  decision records, generation provenance, and CSV export.
- [ ] Add distinct Development, Sales LTR, and Sales RTL Jinja renderers.
- [ ] Add Playwright PDF generation and complete ready validation groups.
- [ ] Add the first-class CLI, including default review stop and explicit fast mode.
- [ ] Add guarded inventory/snapshot/restore/dry-run/migration/reconciliation commands.
- [ ] Update README and compatibility entry points after the new engine is available.

## Test

- [ ] Unit tests for facts, profiles, classification, fit, claims, status transitions,
  filenames, repositories, and invariants.
- [ ] Integration tests for the full default and fast workflows.
- [ ] Development, English Sales, Hebrew Sales, and Tech Sales golden fixtures.
- [ ] Rendering, page-count, overflow, RTL/LTR, mixed-direction, link, and ATS tests.
- [ ] Migration fixture tests proving row/artifact preservation and deterministic
  mapping.
- [ ] Add targeted regressions for material implementation bugs.

## Migrate

- [ ] Generate the complete legacy inventory and anomaly report.
- [ ] Create a timestamped full snapshot and manifest.
- [ ] Write restore instructions and verify restoration into a temporary directory.
- [ ] Prove migration tests pass and dry-run migration against the restored copy.
- [ ] Verify every row and historical artifact is accounted for.
- [ ] Create modular canonical fact sources with the Section 7 corrections.
- [ ] Apply CSV-to-SQLite migration without modifying legacy files.

## Verify

- [ ] Reconcile hashes, paths, database relationships, row counts, statuses, events,
  snapshots, and artifact versions.
- [ ] Run the complete test suite and acceptance command.
- [ ] Exercise a full CLI Definition-of-Done flow without a Web UI.
- [ ] Report every acceptance item as pass, fail, or remaining with evidence.
