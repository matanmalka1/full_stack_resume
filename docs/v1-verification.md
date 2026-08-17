# v1 Verification Record

Verified: 2026-08-16

Refreshed for the v2 baseline: 2026-08-17

## Outcome

The v1 upgrade passes the binding Definition of Done. No acceptance item failed and no
required work remains. Historical artifacts were not overwritten.

## Test and rendering evidence

- Complete suite: **35 passed** at the original v1 verification; **131 passed** with
  `CV_REQUIRE_BROWSER=1` at the final v2 baseline refresh (2026-08-17).
- Test layers: unit, default and fast integration, four golden profiles, browser/PDF
  rendering, ATS extraction, RTL/LTR and mixed direction, links, migration, legacy
  compatibility, provider contracts, and targeted regressions.
- The actual CLI fast-mode test completes ingest, analysis, drafting, validation,
  approval, HTML/PDF rendering, all ready checks, SQLite tracking, and `ready` without a
  Web UI.
- Drafts are bound to one exact Application -> JobSnapshot -> JobAnalysis chain.
  Cross-application records, stale material analyses, changed approved sources, and
  mismatched artifact/decision ownership fail before approval or `ready`.
- Golden PDFs were generated for Development, English Sales, Hebrew Sales, and Tech
  Sales. All were one page, passed DOM overflow and PDF extraction checks, and their
  screenshots were visually inspected with no clipping, overlap, hierarchy, spacing,
  bullet, or direction defects.

## Knowledge and product evidence

- Four modular sources contain 86 unique stable fact IDs.
- Fact-store SHA-256 version:
  `060a9a7f830c50dd351a7e46a09e4f64707ecbacd4089d05a106e4b4b90b9ba0`.
- Ten Profiles cover Development, all required Sales Profiles, Tech Sales, and
  Pre-Sales/Solutions Consultant.
- Profile-store SHA-256 version:
  `2147421c57e72a62af40979d708387c54cefeda851b01997887cdc87314f62c1`.
- Canonical Pcom team size is approximately 2-3 representatives.
- Canonical performance wording is approximately 30% over the management period, not
  annual or YoY.
- Canonical role ranges are March 2019-August 2020 and August 2020-January 2025.
- Unsupported claims, stale Pcom wording, pending facts, changed claim hashes, changed
  approved source, unsafe headlines, low fit without override, and unresolved material
  classification ambiguity are hard failures.
- The fact-store version covers the canonical facts and their source versions, so
  staging or confirming a fact cannot invalidate another application's draft, while
  promoting one to canonical does.
- `cv reconcile` fails when a fact's on-disk status disagrees with the last recorded
  lifecycle event, or when a non-canonical fact has no event at all.
- The baseline reconciliation passed against all 127 registered artifact versions,
  with no missing paths, hash mismatches, foreign-key problems, or fact-lifecycle
  disagreements.

## Migration evidence

- Inventory: 22 CSV rows, 110 application artifacts, 3 base artifacts, 113 historical
  output files, no duplicate keys, no unaccounted files, and no problems.
- Inventory hash:
  `a9d01cdf510dfd163a8b862c6f4ce42a1ecc417de69b869d819c934ae81ceadc`.
- Verified snapshot: `data/snapshots/20260816T110851+0000`.
- Snapshot manifest: 1,690 files; hash
  `0b170131018ffeecf3567e9f9e15f6eedfee7326823962209339d5ea735b277c`.
- Snapshot archive hash:
  `f2505e44695759f308e8fe0de5433d2c3e5f9f6c25cd565dab6fbcbae7e6236a`.
- Restore extraction and every manifest hash passed; restore instructions are included
  in the snapshot and `docs/v1-migration-restore.md`.
- Migration-specific tests: 2 passed before apply.
- Extracted-copy dry-run: 22 applications, 22 job snapshots, and 113 artifact versions;
  no problems. Report hash:
  `6ff394e4c32d59bed9a090e6477aed45658e8c1722fe53828cea0ce073a2b112`.
- Live migration: the same 22/22/113 counts, one immutable migration-run record, 44
  status-history records, and all 22 legacy drafts mapped conservatively to
  `preparing`.
- SQLite integrity, foreign keys, disk paths, and all 113 artifact hashes reconcile.
- CSV export produced a header plus all 22 application rows.
- Snapshot and live hashes for `base/cv_base.md`, `jobs/status.csv`, and the CodeValue
  Markdown/PDF match exactly, demonstrating that historical evidence was not modified.

## Final acceptance checklist

- [x] Modular Common, Sales, Development, and Situational fact sources exist.
- [x] Every migrated fact has one canonical location and stable identity.
- [x] Canonical Pcom facts match Section 7, not stale legacy claims.
- [x] Development behavior remains supported after migration.
- [x] Sales and Tech Sales Profiles work with dynamic Emphasis.
  - Originally checked against classification only. Emphasis was stored and validated
    but never reached content selection: a Profile's `fact_ids` were a fixed output
    list, so four Emphases produced identical Markdown bodies. Closed by
    `cv_engine/selection.py`; `tests/test_selection.py` now fails if any two Emphases
    for one Profile yield the same selected facts.
- [x] Classification returns Track/Profile/Emphasis, confidence, rationale, and supports
  recorded overrides.
- [x] High/medium/low fit and hard-gap behavior work as specified.
- [x] Pending/confirmed/canonical lifecycle is enforced.
  - Originally checked against `FactStore.promote` alone. The transition rules were
    correct but unreachable as a product: nothing persisted a status change, no CLI
    could request one, no workflow produced a pending fact, and all 85 facts shipped
    canonical, so the lifecycle could never run outside a test. Closed by persistence
    into the canonical `base/` sources, the `fact_events` audit table, the `cv fact`
    commands, claim capture, and Profile attachment; `tests/test_fact_lifecycle.py`
    covers the path from an unsupported manual edit to a selected canonical fact,
    including across process boundaries.
- [x] Unsupported claims block approval and fast mode.
- [x] English and Hebrew CV generation work.
- [x] Hebrew RTL and mixed-direction checks pass.
- [x] Sales has a distinct dynamic rendering schema.
- [x] Default review-before-rendering and explicit fast mode work.
- [x] HTML and PDF are generated from exact approved source through the engine.
- [x] `ready` requires content, profile, structure, page, PDF, ATS, link, visual,
  direction, filename, and metadata checks.
- [x] Recruiter-facing filenames use normalized target roles.
- [x] SQLite stores all required mutable and immutable entities.
- [x] CSV export works.
- [x] Approved/submitted artifact version and immutability behavior is enforced.
- [x] Provider-neutral task interface and a strict OpenAI Responses adapter exist and
  pass request/structured-output contract tests.
- [x] Prompts, contracts, and execution versions are traceable.
- [x] Unit, integration, golden, rendering/ATS, migration, and regression tests pass.
- [x] A complete verified legacy snapshot exists.
- [x] Historical Development and CodeValue artifacts are preserved.
- [x] Migration reconciliation reports no missing or unaccounted data.
- [x] The CLI completes the v1 Definition of Done without a Web UI.

## Failures and remaining work

- Failed acceptance items: none.
- Required remaining v1 work: none.
- Deferred work remains exactly the out-of-v1 list in the binding handoff.
