# Multi-Track CV Engine v1

Fact-safe CV generation and application tracking for Development, Sales, and Tech
Sales. The product is CLI-first; no Web UI is required.

The binding specification is [`docs/v1-upgrade-handoff.md`](docs/v1-upgrade-handoff.md).
Architecture, review evidence, and the staged plan are in `docs/v1-architecture.md`,
`docs/v1-review.md`, and `docs/v1-implementation-plan.md`.

## Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -e '.[test]'
```

PDF generation uses Playwright. The engine will use local Google Chrome when present;
otherwise install Playwright Chromium:

```bash
./.venv/bin/playwright install chromium
```

## Architecture

- `base/common.md`, `base/sales.md`, `base/development.md`, and
  `base/situational_skills.md` are the modular canonical fact store after migration.
- `profiles/` selects and weights facts without duplicating content.
- `rendering/rules/` and `rendering/templates/` define Development, Sales LTR/RTL,
  and deterministic profile-specific presentations of canonical facts. Tech Sales
  can therefore shorten Development evidence into business-value wording without
  changing or duplicating the underlying fact.
- `cv_engine/` owns deterministic workflow, validation, persistence, rendering, AI
  boundaries, and migration.
- `data/applications.sqlite3` stores mutable application state and immutable history.
- `artifacts/working/` contains replaceable working drafts; approved/rendered versions
  are immutable version directories under `artifacts/<application-id>/`.
- Legacy files under `outputs/`, `jobs/status.csv`, and `base/cv_base.md` remain
  immutable historical evidence.

## Default workflow

Create the application and immutable job snapshot:

```bash
./.venv/bin/cv ingest \
  --company 'Example' \
  --role 'Account Manager' \
  --job-file /path/to/job-description.txt \
  --url 'https://example.com/job'
```

Use the returned application ID:

```bash
./.venv/bin/cv analyze <application-id>
./.venv/bin/cv draft <application-id>
./.venv/bin/cv validate <application-id>
```

`draft` stops for review. It never renders by default. Manual edits are classified as
exact canonical wording, a versioned deterministic composite, conservatively
extractive derived wording, or a pending claim that blocks approval. Edit one claim
through the unified CLI flow with:

```bash
./.venv/bin/cv edit-claim <application-id> <claim-id> \
  --text 'A complete clause preserved from the canonical rendering' \
  --fact-id sales.cycle.discovery

./.venv/bin/cv edit-claim <application-id> <claim-id> \
  --template canonical-renderings \
  --fact-id sales.metric.recurring_customers \
  --fact-id sales.metric.performance
```

Edits made directly to existing marked claim lines in `resume.md` are extracted and
classified by `validate`, or explicitly with `cv sync-draft <application-id>`. Structural
Markdown edits or removed markers remain hard failures. Unsupported wording is retained
as `pending`; it is never silently discarded and cannot be approved.

Then approve, render, and inspect the complete ready result:

```bash
./.venv/bin/cv approve <application-id>
./.venv/bin/cv render <application-id>
./.venv/bin/cv ready <application-id>
```

Explicit fast mode removes the review pause but runs the same content, claim,
rendering, PDF, ATS, link, direction, filename, and visual gates:

```bash
./.venv/bin/cv fast \
  --company 'Example' \
  --role 'Account Manager' \
  --job-file /path/to/job-description.txt
```

Low fit and material classification ambiguity stop by default. Record explicit
overrides through `analyze --track ... --profile ... --emphasis ...` and, when the user
accepts a low fit, `--accept-low-fit`. Overrides never authorize fabricated facts.

Emphasis is a content decision, not a label. A Profile's `fact_ids` are the candidate
pool a section may draw from, and `config/emphasis.json` weights the canonical fact tags
per Emphasis, so the same Profile produces a different CV under `account-growth` than
under `new-business`. Selection is deterministic and recorded: `resume.claims.json`
carries the score, outcome and omission reason for every candidate considered. Because
Emphasis now changes the document, a disagreement about it between the deterministic
classifier and an AI proposal requires an explicit `--emphasis` decision.

The analyzer also normalizes job language such as outbound, discovery, closing, CRM,
pipeline, integrations, and onboarding into the canonical tag vocabulary. Unverified
direct SaaS Sales, named Sales-CRM usage, and strategic-partnership ownership remain
recorded gaps; verified substitute facts may be selected, but the missing experience
is never inferred from them.

## Fact lifecycle

New information is never written straight into a CV. It enters the store as a `pending`
fact, is confirmed, is promoted to `canonical`, and only then may a Profile section offer
it to the selection policy. Every step writes to the canonical source file under `base/`
and appends an immutable event to `fact_events` in SQLite, so the status survives the
process and the trail explains who promoted what.

```bash
./.venv/bin/cv fact list --status pending
./.venv/bin/cv fact add \
  --source situational_skills.md \
  --fact-id situational.sqlite \
  --meaning 'Used SQLite for local application state in a personal project.' \
  --en 'Used SQLite for local application state in a personal project.' \
  --tag development --tag situational \
  --style bullet \
  --provenance 'candidate wording from the user; not yet verified'
./.venv/bin/cv fact confirm situational.sqlite --confirm
./.venv/bin/cv fact promote situational.sqlite --confirm
./.venv/bin/cv fact attach situational.sqlite --profile development --section 'Technical Skills'
./.venv/bin/cv fact show situational.sqlite
./.venv/bin/cv fact history
```

A manual draft edit the fact store cannot support becomes a `pending` claim that blocks
approval. Capture its wording as a candidate fact instead of retyping it:

```bash
./.venv/bin/cv fact capture <application-id> <claim-id> \
  --source sales.md \
  --fact-id sales.leadership.pipeline_review \
  --meaning 'Introduced a weekly pipeline review with the Sales team.' \
  --tag sales --tag leadership
```

`--confirm` is required for every promotion, and `pending -> canonical` in one step is
refused. Only `cv fact add`/`capture --canonical` — the specification's explicit "add this
to the source of truth" — may write a fact as canonical immediately. Until a fact is
canonical it cannot be rendered, linked to a claim, or attached to a Profile, and adding
or confirming one never invalidates drafts already built from the canonical facts.
Promoting one to canonical does change the canonical surface, so rebuild the working
draft with `cv draft <application-id>` afterwards.

## Tracking and inspection

```bash
./.venv/bin/cv list
./.venv/bin/cv show <application-id>
./.venv/bin/cv versions <application-id>
./.venv/bin/cv decision <application-id>
./.venv/bin/cv status <application-id> applied --reason 'Submitted to employer'
./.venv/bin/cv action <application-id> --next-action 'Follow up' --date 2026-08-20
./.venv/bin/cv export data/applications.csv
./.venv/bin/cv reconcile
```

Marking an application `applied` records the exact validated PDF version as the
submission. Status history and submission records are append-only.

## Optional AI provider

The deterministic engine completes the entire workflow offline. To request an OpenAI
classification proposal through the provider-neutral structured task contract:

```bash
export OPENAI_API_KEY='...'
./.venv/bin/cv analyze <application-id> --provider openai --model gpt-5.6
```

Provider output is Pydantic-validated and deterministic hard gaps remain authoritative.
The adapter uses strict Structured Outputs through the Responses API.

## Guarded migration

Run these commands in order. `apply` refuses to run unless the exact inventory,
snapshot, restored-copy verification, migration test report, and dry-run report all
agree.

```bash
./.venv/bin/cv migrate inventory
./.venv/bin/cv migrate test
./.venv/bin/cv migrate snapshot
./.venv/bin/cv migrate verify-snapshot --snapshot data/snapshots/<timestamp>
./.venv/bin/cv migrate dry-run --snapshot data/snapshots/<timestamp>
./.venv/bin/cv migrate apply --snapshot data/snapshots/<timestamp>
./.venv/bin/cv migrate reconcile
```

For a migration that was completed before the hardened gate existed, reproduce the
current migration against the pre-migration snapshot in a temporary directory and
compare its database semantics, migrated facts, and historical artifact hashes to the
live state without modifying it:

```bash
./.venv/bin/cv migrate verify-live --snapshot data/snapshots/<timestamp>
```

Every fact the migration produced must still exist unchanged in the same canonical
source file; facts added afterwards through the fact lifecycle are reported under
`post_migration_facts` and are not drift.

The tracked result for the completed v1 migration is
[`docs/v1-retrospective-migration-verification.json`](docs/v1-retrospective-migration-verification.json).

Restore instructions are in
[`docs/v1-migration-restore.md`](docs/v1-migration-restore.md). Never extract a snapshot
over the live repository.

## Tests

```bash
./.venv/bin/python -m pytest -q
```

The suite covers unit contracts, default workflow, golden Development/English
Sales/Hebrew Sales/Tech Sales cases, RTL/LTR rendering, PDF/ATS checks, migration,
immutability, and targeted regressions.

Thirty tests start a real headless Chromium/Chrome and are marked `browser`. Some
sandboxed agent sessions (for example Codex under Seatbelt) block the browser's Mach
port registration, so the browser cannot start there at all; Chrome's `--no-sandbox`
flag does not help, because it only disables Chrome's own sandbox. Trusted Codex
sessions load `.codex/rules/pytest.rules` at startup, allowing only the project pytest
prefix to run outside Seatbelt. Restart Codex after first checking out the rule.

When that rule is unavailable, run the subset that needs no browser:

```bash
./.venv/bin/python -m pytest -q -m "not browser"
```

That is a reduced run, not a complete one. Rendering, PDF, and ATS checks are
acceptance requirements, so the full suite must still run in a normal terminal or in
CI before `ready` or completion. Set `CV_REQUIRE_BROWSER=1` there: the run then fails
immediately if the browser tests were deselected.

## Historical artifacts

The pre-v1 generation scripts have been retired. Legacy files under `outputs/`,
`jobs/status.csv`, and `base/cv_base.md` remain immutable historical evidence and must
not be hand-edited, overwritten, or used as the active tailoring workflow. New work
uses `cv` exclusively.
