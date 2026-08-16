# v1 Repository Review

Reviewed: 2026-08-16

This review records the pre-implementation state. It is evidence for the migration
inventory, not permission to alter historical artifacts.

## Current state

- The worktree was clean at review start.
- The repository is a legacy Development-only, file-driven workflow.
- `jobs/status.csv` contains 22 application rows, all with legacy status `draft`.
- Disk contains 22 matching application artifact sets. Each set has a job snapshot,
  Markdown draft, notes, HTML, and PDF.
- A separate base CV artifact set contains Markdown, HTML, and PDF but is not an
  application and therefore has no CSV row.
- There are 23 PDFs under `outputs/`; `file` recognizes every one as a one-page PDF.
- The tracked `outputs/archive/` directory is empty except for `.gitkeep`.
- The legacy reconciliation tool reports only the expected untracked-as-application
  base draft.

## Known anomalies that migration must preserve

1. The CodeValue Sales Development Representative artifact was produced as an
   explicitly documented off-pipeline exception. Its Markdown does not conform to the
   Development-only validator, and its facts and dates include values superseded by the
   binding v1 specification. The files remain immutable historical evidence.
2. The Helfy draft uses a legacy base-CV layout and fails the current output skeleton.
   Its existing HTML and PDF remain historical evidence.
3. The base artifact set is not an application. Migration must inventory it as a
   historical reference artifact without inventing an application row.
4. Legacy Development drafts commonly contain the stale Pcom team-size and annualized
   growth wording inherited from `base/cv_base.md`. They must not be rewritten in place
   and must not be promoted to v1 `ready`.
5. `other_clients/` contains a separate person's CV files. They are outside the Matan
   Malka application store but must be included in the repository snapshot so the
   backup is complete.

## Baseline behavior and dependency state

- `build_html.py` has a fixed Development title whitelist, fixed section sequence, and
  a single non-Jinja HTML template.
- `print_pdf.sh` shells out to a local Chrome executable and uses a fixed recruiter
  filename.
- `check_status.py` knows only CSV and the legacy `draft`/`sent` semantics.
- No project dependency manifest or test suite exists.
- The active Python is 3.14.2. Pydantic, Jinja2, Playwright, and Poppler tools were not
  available in the initial environment inspection.

## Migration interpretation

- All 22 legacy `draft` rows deterministically map to `preparing`. Existing artifacts
  alone cannot establish v1 `ready`, whose content, profile, structure, PDF, ATS, link,
  direction, filename, and visual checks did not exist when these files were created.
- No legacy `date_sent` value is populated, so migration must not infer a submission.
- Every historical file is registered by its original relative path and SHA-256 hash.
- The original job-description file is the immutable first job snapshot.
- Existing Markdown, notes, HTML, and PDF files are historical artifact versions and
  must never be overwritten, renamed, or normalized in place.

## Review conclusion

No product-specification contradiction or semantic blocker was found. Implementation
can proceed, subject to the mandatory migration gate: inventory, complete verified
snapshot, restore instructions and restore verification, passing migration tests, and
accounting for every legacy row and artifact before live migration.
