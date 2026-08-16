# v1 Architecture

This architecture implements `docs/v1-upgrade-handoff.md` without changing its product
semantics.

## Boundaries

The engine is divided into four explicit layers:

1. Canonical facts in `base/*.md`, each with one stable ID, lifecycle state,
   provenance, dates, tags, language-neutral meaning, and approved renderings.
2. Profiles in `profiles/**/*.yaml`, which reference facts and tags and supply weights
   without copying fact content.
3. Rendering policy in `rendering/rules/*.yaml` and Jinja templates in
   `rendering/templates/`.
4. Mutable workflow state in `data/applications.sqlite3`; generated and historical
   artifacts remain files referenced by hash and relative path.

JSON-compatible YAML is used so the files remain readable YAML while the v1 runtime
does not need a second configuration parser dependency.

## Domain core

`cv_engine` owns Pydantic contracts for facts, profiles, classifications, fit results,
claims, drafts, validation results, artifacts, decision records, and provider tasks.
Critical state is never inferred by parsing unconstrained model prose.

The deterministic core owns:

- fact identity, lifecycle, and duplicate-location checks;
- Track/Profile/Emphasis enums and override precedence;
- confidence routing and hard-gap behavior;
- selected-fact authorization and claim linkage;
- workflow/status transitions;
- approval and fast-mode safety gates;
- normalized filenames;
- persistence, artifact immutability, rendering checks, and migration.

The classification and drafting services can run deterministically for a complete
offline CLI flow. A provider-neutral task interface also includes a real OpenAI adapter
that accepts and returns the shared structured contracts when explicitly configured.
Provider failures and invalid output are explicit failures, never silent fallbacks.

## Claims and manual edits

Generated Markdown contains stable claim markers, and its sidecar claim manifest binds
each rendered statement to canonical fact IDs and an exact text hash. Wording-only or
derived manual text must be registered through the claim-extraction/linkage workflow.
Unmarked text, changed text, nonexistent facts, noncanonical facts, and unresolved
pending facts are hard failures before approval and in fast mode.

This deliberately favors false negatives over allowing an unsupported candidate claim.

## Persistence and immutability

SQLite uses foreign keys, transactions, uniqueness constraints, and immutability
triggers. It contains the required concepts:

- applications and immutable status history;
- immutable job snapshots and versioned analyses;
- application events and next actions;
- artifacts and meaningful artifact versions;
- decision records and generation runs;
- recorded validation runs and migration runs.

Approved, rendered, submitted, and migrated-historical artifact versions are append-only.
Submitted paths and hashes cannot be replaced. Working drafts live in a dedicated
working area and are promoted to versioned files on approval.

## Workflow

The default CLI flow is:

`ingest -> analyze -> draft -> validate -> review stop -> approve -> render -> ready`

Explicit fast mode performs the same validation and promotion steps in one command but
does not pause. Low fit or a hard gap stops generation unless the user records an
override; an override never bypasses factual validation. Ambiguous material
classification similarly requires an explicit override.

## Rendering and ready checks

Development and Sales use separate dynamic schemas. English uses LTR templates; Hebrew
Sales uses full RTL with isolated mixed-direction spans where needed. Jinja generates
HTML from approved source only. Playwright generates PDF and evaluates page geometry,
overflow, clipping, links, and direction. PDF extraction checks page count, corruption,
and normalized source-text coverage. Screenshots are retained as validation evidence
for visual review.

`ready` is set only when every required group passes: content, profile/fit, structure,
page count, PDF generation, ATS extraction, links, visual geometry, direction, and
filename/metadata.

## Migration

Migration is its own guarded subsystem, not a side effect of application startup. It
provides inventory, snapshot, restore verification, dry-run, apply, and reconciliation
commands. The live apply command refuses to run unless a signed gate report proves:

- manifest completeness and verified hashes;
- a restorable timestamped snapshot and restore instructions;
- passing migration tests;
- a successful dry-run against an extracted copy;
- complete accounting for all legacy CSV rows and historical artifacts.

The migration adds new authoritative sources and SQLite state alongside immutable
legacy files. It does not overwrite or delete `base/cv_base.md`, `jobs/status.csv`, or
anything under `outputs/`.
