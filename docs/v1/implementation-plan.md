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

- [x] Add dependency metadata and the Pydantic domain contracts.
- [x] Add fact/profile/rule loaders and duplicate/fact-lifecycle enforcement.
- [x] Add deterministic classification, fit/gap analysis, fact selection, drafting,
  exact claim linkage, overrides, and the provider task boundary.
- [x] Add SQLite schema/repositories, immutable history, status transitions, actions,
  decision records, generation provenance, and CSV export.
- [x] Add distinct Development, Sales LTR, and Sales RTL Jinja renderers.
- [x] Add Playwright PDF generation and complete ready validation groups.
- [x] Add the first-class CLI, including default review stop and explicit fast mode.
- [x] Add guarded inventory/snapshot/restore/dry-run/migration/reconciliation commands.
- [x] Update README and compatibility entry points after the new engine is available.

## Test

- [x] Unit tests for facts, profiles, classification, fit, claims, status transitions,
  filenames, repositories, and invariants.
- [x] Integration tests for the full default and fast workflows.
- [x] Development, English Sales, Hebrew Sales, and Tech Sales golden fixtures.
- [x] Rendering, page-count, overflow, RTL/LTR, mixed-direction, link, and ATS tests.
- [x] Migration fixture tests proving row/artifact preservation and deterministic
  mapping.
- [x] Add targeted regressions for material implementation bugs.

## Migrate

- [x] Generate the complete legacy inventory and anomaly report.
- [x] Create a timestamped full snapshot and manifest.
- [x] Write restore instructions and verify restoration into a temporary directory.
- [x] Prove migration tests pass and dry-run migration against the restored copy.
- [x] Verify every row and historical artifact is accounted for.
- [x] Create modular canonical fact sources with the Section 7 corrections.
- [x] Apply CSV-to-SQLite migration without modifying legacy files.

## Verify

- [x] Reconcile hashes, paths, database relationships, row counts, statuses, events,
  snapshots, and artifact versions.
- [x] Run the complete test suite and acceptance verification.
- [x] Exercise a full CLI Definition-of-Done flow without a Web UI.
- [x] Report every acceptance item as pass, fail, or remaining with evidence.
