# M5 — remaining work

Status: **not started; unblocked on 2026-08-30.** The M4 gate closed by decision rather
than by evidence — `docs/m4-remaining.md` §F records what was retired and what it costs.
M5 therefore starts without a proven built-Web journey behind it: the screens this
milestone adds have no end-to-end safety net, and their own evidence has to carry more
weight than it would have.

Authority for scope and gates is `docs/spec/implementation-plan.md`. This file records
only what M5 must still do; M4's record stays in its own tracker and is not amended here.

## Where things are written

One fact, one place.

| Question | Answer lives in |
| --- | --- |
| What M5 must still do | **this file** |
| What M4 must still do | `docs/m4-remaining.md` |
| Product semantics and UI scope | `docs/spec/product-spec.md` |
| State, action, command, and query contracts | `docs/spec/state-and-use-cases.md` |
| Layer boundaries | `docs/spec/architecture.md` |
| Non-milestone cleanup | `docs/cleanup-todos.md` |

## What already landed

The interface split is done on the backend. The CLI is the runtime and maintenance
surface, and the API carries the product use-cases that used to be CLI-only. What remains
is the Web UI for three of them, and the CLI retirement that follows it.

| Capability | API | Web | CLI command still present |
| --- | --- | --- | --- |
| Fact lifecycle | done (`/api/v1/facts`, 9 routes) | **missing** | `fact` (7 of 8 subcommands) |
| Recruitment tracking | done (5 routes under `/applications/{id}`) | **missing** | `status`, `correct-status`, `submit`, `external-submit`, `action` |
| Provenance export | done (`GET /approved-revisions/{id}/decision-markdown`) | **missing** | `decision-markdown` |
| Claim editing | already covered by `PATCH /working-drafts/{id}` | done | `edit-claim` — redundant, retire with the rest |

`cv fact add` is **not** on the retirement list. `docs/spec/product-spec.md` §17 keeps
canonical corrections — a new fact carrying `replaces` — as a CLI concern in v2.0, and the
UI does not expose fact-ID creation. It stays after M5.

## M5 scope

### 1 — Recruitment tracking UI

The Application context screen shows `recruitment_status` read-only today. Tracking is
five actions, all already served by the API:

- [ ] Transition status. `applied` is submission-owned and is not offerable: the request
      schema excludes it and the application layer refuses it. Only transitions the
      backend allows may be offered — the graph is narrow, and from `saved` only
      `withdrawn` and `closed` are reachable without a submission.
- [ ] Correct a recorded status. Requires the corrected event and a reason; a correction
      appends an event and never edits the one it corrects, so the trail must show both.
- [ ] Record an internal submission. Requires the exact ApprovedRevision and PDF artifact
      IDs. Ready qualification is re-derived at submission time, so a stale or tampered
      revision is refused rather than recorded.
- [ ] Record an external submission. Invents neither a revision nor an artifact; a field
      that cannot be derived stays null in the UI as well as in the record.
- [ ] Set and clear the one active next action. Clearing is a real request, distinct from
      not asking about it.

Surfacing the recruitment timeline is part of this: corrections and submissions are only
meaningful beside the history they amend.

### 2 — Fact lifecycle UI

`docs/spec/product-spec.md` §17 scopes this as a **contextual** flow reached from a draft
claim, not a general Knowledge Manager — the broader Knowledge UI is deferred (§23).

- [ ] View facts and one fact's lifecycle trail.
- [ ] Create a pending fact. Identity is generated; the UI must not offer a fact ID.
- [ ] Capture a fact from an unsupported claim. The claim's exact text becomes the
      rendering, with no AI rewriting; meaning, tags, and provenance are explicit input.
- [ ] Confirm, then promote. Explicit confirmation is required for each, and
      `pending -> canonical` in one step is refused.
- [ ] Attach a canonical fact to a Profile section.
- [ ] `Confirm and use` — one logical command that promotes, attaches, and creates the
      replacement SelectionPlan, or reports a complete failure. The API composite exists
      and has no caller yet.

### 3 — Provenance export UI

- [ ] Offer the decision Markdown beside the revision it explains. The response carries
      `content` and `content_hash`; the suggested save name arrives in
      `Content-Disposition`, not as a body field.

### 4 — CLI retirement

Only after the Web equivalents ship and their gate passes:

- [ ] Delete `fact` (keeping `add`), `status`, `correct-status`, `submit`,
      `external-submit`, `action`, `edit-claim`, `decision-markdown`, their parser
      entries, and the CLI-bound tests and fixtures that remain (`cli_runner`,
      `cli_subprocess`, `run_cli`).
- [ ] Final CLI surface: `web`, `reconcile`, `export`, `fact add`.
- [ ] Update `README.md` and `CLAUDE.md` to the final command list.

## Frontend conventions this work must hold

Established by M4 and enforced by the build, not by review:

- types come from the generated `openapi/types.ts` through `src/api/contracts.ts`;
  regenerate the contract and the types whenever a route changes;
- a label map keyed by a generated union stays exhaustive, so a value added to the
  backend fails the frontend build rather than arriving untranslated;
- `npm run lint:tokens` refuses literal colors and raw palette utilities, and its
  `EXCEPTIONS` list is deliberately empty;
- the UI is Hebrew and RTL with explicit LTR islands for IDs and technical values;
- no screen requires technical IDs, hashes, paths, or architecture knowledge of the user.

## Known consequence carried in from the CLI reduction

`cv sync-draft` was deleted at the user's direction. It imported edits made directly to
the working `resume.md` file, and the v2 use-case list does not include it — claims are
edited through the draft's own autosave.

The data-loss guard it was paired with **stays**: approval still refuses while the
projection holds an edit storage has not imported, because approval rebuilds the
projection from the database and would otherwise destroy that edit without a word. What
changed is the remedy. A user who edits `resume.md` by hand can now only re-apply the
change in the editor or regenerate and discard it.

- [ ] Decide whether the draft editor should surface that refusal as something a user can
      act on, or whether the projection file should stop being writable in a way that
      invites hand editing at all.

## Deferred, not in M5

Named here so they are not rediscovered as gaps: companion application documents,
AI-generated decision explanations, AI-assisted semantic claim linkage, a broader
Knowledge UI, CSV Web export, notifications, calendar integration, analytics, additional
providers, i18n, and hosted or multi-candidate operation (`docs/spec/product-spec.md`
§23).

## Cleanup carried forward

- [ ] The path-shaped contract guard in `tests/test_api_foundation.py` matches on field
      *names* (`*_path`, `*_file`, `*_location`, …). `profile_source` was a real
      repository path that the pattern did not match; it was found by reading values, not
      names, and removed from the wire. The guard has a blind spot, and widening the
      pattern has its own false-positive cost — worth a deliberate decision rather than
      leaving it unrecorded.
