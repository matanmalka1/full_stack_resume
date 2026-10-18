# CV Application Product Specification

What the product does, as implemented. Work not yet built is marked *not built*.
Section numbers are cited from code and tests; keep them stable.

## תקציר

כלי שמתאים קורות חיים למשרה מתוך העובדות של המועמד ומפיק PDF קריא לאדם ול־ATS. כל
משתמש הוא מועמד אחד ורואה רק את המידע שלו (§22).

`Create -> Analyze -> Draft -> Edit -> Check -> Approve -> Render -> Ready -> Submit`

ניתוח וכתיבה דורשים ספק AI; כל השאר עובד בלעדיו. לכל Application יש מסמך קורות חיים
אחד שאפשר לערוך תמיד; אישור ו־Ready נגזרים מהתוכן הנוכחי. Submission מתעד שליחה שנעשתה
מחוץ למערכת.

## 1. Documents

- This file: what the product does and does not do.
- [`state-and-use-cases.md`](state-and-use-cases.md): states, commands, preconditions,
  error codes, HTTP mapping.
- [`architecture.md`](architecture.md): layers, storage, transactions, Operations,
  runtime.
- [`test-and-acceptance-plan.md`](test-and-acceptance-plan.md): tests and release
  checks.

Where another document owns a mechanism, this one links to it instead of restating it.

## 2. Product goal

A signed-in user can create a job application, analyze the job, get and edit a CV
built from their facts, approve it, render an ATS-readable PDF, record what was sent,
and track the recruitment process — through the Web client, without seeing another
user's data. The UI never requires entity IDs, hashes, paths, or architecture
knowledge; those appear only in provenance views.

Development and sales are both supported tailoring targets.

### Semantic analysis authority

`analyze_job` sends the job text and the user's canonical facts to the AI provider,
which proposes the requirements, their importance, coverage with evidence, shortfall
severity, and the Track/Profile/Emphasis/language classification.

The engine then applies the checks it can run itself: each quoted requirement must
occur in the job text, cited facts must exist and be canonical, boundary facts and
Profile legality apply, and requirement identity, gaps, Fit, and review routing are
derived. These checks only lower a proposal, never raise it. What cannot be determined
is `unknown`. `config/requirements.json` supplies boundary applicability and scale
ordering only.

`draft_resume` chooses which facts go in each section and words them (§10). The engine
refuses a fact that is not canonical, not in the section's pool, or has no rendering in
the document language, and keeps the document structure intact. Section budgets, tags,
per-role minimums, and Profile pins are sent as guidance and not enforced.

There is no rules-based analysis or drafting. Without a provider, new analyses and
drafts are unavailable and the UI offers configuration or retry; a provider failure
never falls back silently. Editing, checking, approval, rendering, submission, export,
and tracking all work without a provider.

## 3. Product boundaries

- One candidate per user. Candidate-specific settings come from the user's
  `CandidateContext`; the code contains no candidate names or identities.
- Facts, CandidateContext, and each user's Profile binding (section pools, pins,
  headlines, omitted roles) live in PostgreSQL per user. Profile templates, emphasis
  policy, prompts, task contracts, requirement concepts, and rendering rules are
  version-controlled files (`profiles/`, `config/`, `ai/`, `rendering/`). `base/` is
  import input only.
- React is the interface; FastAPI is the only user-facing adapter. The worker executes
  Operations through the same application layer.
- Two processes (API and worker) over one PostgreSQL database, authentication always
  on. *Not built:* hosted deployment over HTTPS; today it binds to loopback.
- macOS is the primary target. The UI supports current Chrome/Chromium; PDFs render
  with Playwright-managed Chromium.

## 4. Scope

- Hebrew, RTL, desktop-first Web UI with light/dark/system theme and quick application
  switching.
- Job intake: company, role, pasted text, optional URL, `.txt` file read in the
  browser, and a browser-local recovery copy of the unsent form.
- Duplicate warnings with explicit acknowledgement (§8).
- Editable job text, locked by the first Submission (§8).
- AI job analysis with requirements, coverage, gaps, Fit, and issues; a form to change
  Track, Profile, language, and Emphasis.
- One mutable CV document per Application: AI drafting, a section/claim editor with
  autosave, reordering within a section, undo/redo, section and claim regeneration,
  review of a user-written line, and HTML and draft-PDF previews.
- Content check, explicit approval, rendering with PDF/ATS validation, and Ready.
- Facts screen ("מאגר העובדות"): list, inspect, create pending, confirm, delete, attach
  to Profile sections; create a fact from a claim; `Confirm and use`. *Not built:*
  editing a fact in place (§17).
- Dashboard with search, filters, presets, facets, and sorting; Application Detail with
  preparation state, blockers, next action, notes, timeline, and submissions.
- Recruitment status, corrections, one next action with overdue warning, internal and
  external submissions, close, soft delete.
- Recruiter PDF download and a provenance Markdown export.
- Cancellable, retryable Operations for AI work and rendering.
- Settings (§15), a health endpoint, and operator maintenance commands (§16).

## 5. Explicit non-goals

- More than one candidate per user; roles, teams, sharing, or an admin UI.
- Self sign-up, email verification or reset, SSO, MFA, social login, or running without
  authentication.
- Sync, extra databases, or an ORM.
- Fetching jobs from URLs or LinkedIn, parsing job PDFs, arbitrary uploads or imports.
- Rules-based analysis, other AI providers, arbitrary model IDs, or user prompts.
- Cover letters, messages, emails, or other document types.
- AI extracting facts from edited text on its own.
- Web editing of Profiles, policies, prompts, or rules.
- Archive or retirement states for facts.
- WYSIWYG editing, section reordering, drag-and-drop.
- CV revision history or version comparison (Submissions are the history of what was
  sent).
- Mobile-first flows, notifications, calendar, charts, analytics, CSV export,
  WebSocket/SSE progress, automatic updates, built-in backup.

## 6. Core invariants

1. An `Application` holds one target job and its history.
2. Every record belongs to exactly one user, directly or through its Application.
   Another user's record behaves exactly like a missing one (§22).
3. Each Application has exactly one `CVDocument`, created with its first analysis.
4. JobAnalysis, AI call records, Submissions, recruitment/audit/fact events, and
   finished Operations are immutable, and job text is locked once submitted. Database
   triggers enforce this.
5. Editing an approved or Ready document is always allowed and returns it to draft.
6. Approval and Ready are derived on read by comparing `approved_basis` and
   `rendered_basis` with the current `basis` (state-and-use-cases.md §3–§4).
7. The basis covers the document content, its analysis pin, and the current state of
   every fact it uses. Changing any of them outdates every stamp.
8. Approval requires a passing content check of the exact current basis.
9. Unsupported, pending, unlinked, or unreviewed claims can be saved but block approval.
10. Wording is supported only by a deterministic proof or a passing review (§10.1).
11. AI output is a proposal; validation and an application commit decide what becomes
    state.
12. AI failure never falls back silently. A withheld line (§10.1) keeps its previous
    wording and is reported.
13. Provider, cancelled, or stale output becomes state only through a successful commit
    against its original preconditions. Every provider call is logged either way.
14. Preparation and recruitment are independent lifecycles.
15. Recruitment history is append-only; corrections add events.
16. A Submission's content and files are never overwritten, moved, or deleted.
17. No mutable content has two sources of truth.
18. Nothing deletes an immutable payload.
19. Queries never expose a partially committed mutation.
20. `delete_application` and `delete_fact` are soft deletes. A deleted item leaves
    default listings but stays reachable by ID with its records preserved.
21. Concurrency is handled by the document hash, optimistic versions, unique-index
    claims, idempotency keys, and commit-time precondition checks.
22. A fresh installation starts with an empty database and no users.
23. Commands name their sources; only queries resolve "latest".

## 7. Candidate and application behavior

Each user has one CandidateContext. It points to the user's name and contact facts
(with track-specific contacts, such as GitHub for development) and sets filename
language, locale, timezone, and link schemes.

The recruiter-facing filename uses the candidate name in the filename language (English
by default), including for a Hebrew CV.

Artifacts, temporary files, and logs live in fixed directories under the installed
project root (architecture.md §4).

## 8. Job intake and job text

The intake form requires company, role, and job text; the URL is optional. Notes belong
to Application Detail.

The form keeps a browser-local recovery copy that survives reloads; errors never
discard entered values. A successful creation clears the copy.

`create_application` is synchronous and calls no AI. It stores the exact text with a
hash (`job_text_hash`) and a normalized hash for deduplication. A `.txt` file only fills
the text area. The URL is stored for reference, never fetched, and must be `http(s)`.

Duplicates (same URL, same normalized text, or similar company/title) are checked before
and inside creation, excluding deleted Applications. An unacknowledged match is refused
(`DUPLICATE_ACKNOWLEDGEMENT_REQUIRED`, 412); resending with acknowledgement creates the
Application, or the user can open the existing one.

After creation the Web client queues `analyze_job`. If that fails, Analyze stays
available.

A changed posting is edited in place (`update_job_text`), naming the text it replaces by
hash; there is no version history. Earlier analyses stay on record, Analyze becomes
available, and the document reports `DOCUMENT_ON_OLDER_ANALYSIS` until the user runs
`build_from_analysis` on a newer analysis.

The first Submission, internal or external, locks the job text.

## 9. Analysis and review

A JobAnalysis holds classification, requirements, coverage, and analysis issues. Fit
and gaps are computed from its requirements. Each analysis is immutable.

The first successful `analyze_job` also creates the empty CVDocument pinned to it. A
later analysis does not touch the document; it shows `DOCUMENT_ON_OLDER_ANALYSIS` until
`build_from_analysis` re-pins the document and clears its content and stamps.

The facts a document uses are the facts its content links; they are chosen during
drafting (§10) and changed by editing.

The matching form (`apply_analysis_decisions`) changes Track, Profile, language, or
Emphasis by creating a new JobAnalysis without calling the provider.

Fit, gaps, and analysis issues are shown but never block anything. An uncertain
requirement stays `unknown`.

Review reasons — a fact the document uses that is pending or deleted
(state-and-use-cases.md §7) — block approve, render, and submit.

When automatic generation is on (off by default), the analysis that creates the
document also queues `create_draft`, with the model and effort fixed at submission.
The Web client follows it into the editor.

## 10. Drafting and editing

Document content is the structured DraftDocument in `cv_documents.content`; Markdown and
HTML are generated from it.

`create_draft` is an AI Operation, available while the document has no content. The
engine sends `draft_resume` each Profile section's pool (every canonical fact with its
rendering in the document language), the structural facts, and the section's guidance:
claim budget, per-role minimums and ceiling, tags and weights, and Profile pins.
`draft_resume` chooses and words the facts. A fact outside the pool or not canonical is
refused; a chosen fact with no rendering in the document language fails the draft
(`MISSING_FACT_RENDERING`). Guidance is not enforced. Chosen facts are laid out in pool
order so each role keeps its title, dates, and bullets together. New wording goes
through §10.1.

The editor shows sections and claims; each claim has its text, linked facts, status,
warnings, and edit, regenerate, and remove controls. Section order comes from the
Profile; claims can be reordered within a section. Undo/redo is client-side. The
headline must be one of the Profile's safe headlines.

Any claim can be removed. Free-text edits are always saved; unsupported ones are marked
unsafe and block approval until they are supported (§10.1), resolved through the fact
lifecycle (§17), or removed. Unlinked text needs fact links before review. AI never
turns edited text into a fact.

`regenerate_section` and `regenerate_claim` rewrite through the same writer-and-reviewer
path. `regenerate_claim` with `keep_text` sends the user's own line to review as
written.

For reviewed wording the editor shows the review's assertion-to-source excerpts,
labeled as AI review, and warns that editing the wording invalidates it.

Autosave uses the document hash as ETag. A stale save is a conflict: the UI shows both
versions and the user chooses.

The HTML preview and the on-demand draft PDF render the current content without
approval and store nothing.

### 10.1 Reviewed wording

Wording may paraphrase, shorten, or combine canonical facts without changing their
meaning, and may not add a relationship, cause, employer, time period, or experience
level.

Canonical, extractive, and presentation wording is proven deterministically. Any other
wording passes the hard checks (numbers, dates, sources) and a separate AI review
(`assess_claim_support`) that must account for every factual assertion. A line is
accepted only when every assertion is `supported` and the evidence passes the
deterministic check (`cv_engine/domain/claim_review.py`). Accepted wording needs no
per-line user confirmation.

Writer and reviewer run in one Operation, judged line by line. A line that fails is
*withheld*: it keeps the wording it had before (for a first draft, its frame line built
from canonical facts). Passing lines are written and the Operation lists the withheld
ones. If every line is withheld the Operation fails with `CLAIM_REVIEW_UNSUPPORTED`,
`CLAIM_REVIEW_UNCERTAIN`, or `INVALID_OUTPUT`, and the document is unchanged.

A withheld or rejected line opens a clarification panel: the sentence, its section, the
facts the review read, and the reviewer's explanation, as recorded at the time. The user
can keep the document, edit or remove the line, retry, or add facts. There is no manual
override that accepts a rejected line.

## 11. Validation, approval, rendering, and Ready

Editing runs light checks. `check_document` runs the full content check;
`approve_document` runs the same check and approves if it passes. Neither calls AI.

The content check verifies each claim's proof or review evidence against current facts
and policy versions, plus section placement and fact eligibility. A failed check returns
`passed = false` with issues. Only the latest report is kept, marked outdated once the
basis moves.

Warnings never block. Anything that needs a decision is a blocker or review reason.

Approval is an explicit user action that stamps `approved_basis` and `approved_at`.

Rendering is an Operation, available while the document is approved. It revalidates,
renders HTML and PDF, and checks layout, page count, extracted text, links, direction,
and filename metadata. Success stamps `rendered_basis`; failure keeps the approval and
shows the reason.

A document is **Ready** when `approved_basis` and `rendered_basis` both equal the current
basis.

In the Web editor, rendering starts automatically after the user approves. No chained
flow bypasses a blocker.

The Ready screen shows the preview, PDF download, content report, and provenance, and
offers editing and submission.

## 12. AI behavior

One OpenAI adapter (Responses API, strict Structured Outputs) implements the
`AIProvider` port. Tasks are defined in `ai/contracts/task_contracts.json` with the
prompt `ai/prompts/system.md`:

- `propose_analysis` — requirements, coverage, shortfall, and classification.
- `draft_resume` — facts chosen per section and their wording.
- `regenerate_section`, `regenerate_claim` — targeted rewording.
- `assess_claim_support` — the reviewer for every writing Operation.

**Tolerant reading.** A flawed part of an analysis is narrowed and recorded as an
issue; only an unparseable response fails. A quotation the engine cannot locate is kept
as unverified; an ambiguous one becomes `unknown`.

**Coverage.** `partial` means the facts answer part of a requirement. A mandatory
requirement is a hard gap when `unsupported`, or `partial` with `material` shortfall.
Qualitative words (strong, deep, daily) are judged from the facts, and their absence is
not a shortfall. Fit arithmetic: state-and-use-cases.md §13.

**Context.** Calls are stateless and receive only the job text, the relevant facts, the
Profile catalogue, and task policy. The UI tells the user that job text and facts are
sent to the provider.

**Configuration.** `OPENAI_API_KEY` comes from the environment only and is never
stored, sent to React, or logged. Models come from a backend allowlist; reasoning effort
is `low`/`medium`/`high`; both are fixed when an Operation is queued.

**AI call log.** Every provider call attempt is appended to `ai_calls`: sanitized
response and its hash, model, outcome, error, usage, latency, contract and prompt
versions, price snapshot, and cost. The request is stored only as a hash. Unreported
usage is unknown, not zero. Quota exhaustion (`PROVIDER_QUOTA_EXHAUSTED`) is reported
separately from rate limits. A call is retried at most once, only when that cannot
duplicate a processed request (architecture.md §11). An answer the engine refuses - an analysis it
cannot classify, a draft that leaves a heading empty - is sent back once with the
reason (a repair, architecture.md §11).

**Untrusted input.** Job text and user content are data; instructions inside a posting
are not followed and do not count as requirements.

## 13. Preparation and recruitment

`preparation_state` (`needs_analysis`, `ready_to_draft`, `draft_in_progress`,
`approved`, `ready`) and recruitment status are separate (state-and-use-cases.md §4,
§10). Preparation commands never change recruitment status.

Every Application projection carries preparation state, content-check state, review
reasons, warnings, Operations, document ID/hash/analysis pin, available and blocked
actions with reasons, and a recommended action (state-and-use-cases.md §9). The backend
owns action policy; React does not duplicate it.

## 14. Recruitment tracking

The Dashboard is a table with search, filters, presets (needs attention, ready to send,
active interviews), facet counts, sorting, and paging.

Application Detail shows status, next action, notes, preparation and blockers, a
unified timeline, the document, and submissions.

`submit_application` records a send that already happened outside the system. It
requires a Ready document, copies its content, HTML, and PDF (with SHA-256) into an
immutable Submission, locks the job text, and moves `saved -> applied`. Multiple
submissions are allowed and never change the document.

`record_external_submission` records a send made without the system: no content or
files, same `saved -> applied` rule.

Other status transitions follow the allowed graph; a wrong status is fixed by a
correction event with a reason. One next action and date may be active; overdue is a
computed warning.

Applications can be closed or soft-deleted; there is no hard delete.

Audit events record `actor_type` (`user` | `system`) and `client` (`web` | `worker`).

## 15. Runtime and security

UI and API share one origin. Every route except sign-in and health needs a session.
Mutations validate `Origin`; CORS uses an explicit list (architecture.md §14). *Not
built:* the hosted Host allowlist.

Per-user settings (optimistic, a stale write is a conflict):

- `auto_generate_when_review_not_required` (§9), off by default;
- `default_ai_model` and `default_reasoning_effort`, from allowlists;
- `ui_theme`, `ui_density`, `ui_text_size`.

`provider_configured` is read-only; AI actions are disabled without a provider.

## 16. Storage, provenance, and retention

Storage layout: architecture.md §6. Storage keys and paths are never API inputs.
Downloads are by ID, verify the hash, and use a friendly filename.

**Submission.** Stores the document `content`, `document_hash`, `job_text_hash`, the
HTML and PDF with SHA-256, `submitted_at`, and metadata. It does not store `facts_hash`,
CandidateContext, or policy versions.

**Document provenance.** `built_with` (Profile version) drives the `PROFILE_CHANGED`
warning. `facts_hash` covers only the facts the document uses.

**Retention.** Submissions, their files, locked job text, and the AI call log are kept
forever. Replaced document content is not archived; superseded rendered files are
deleted.

**Maintenance.** Operator CLI commands, across all users: reconciliation verifies
payload and AI-log hashes and the fact trail and repairs nothing; orphan inspection
lists unreferenced payloads older than one hour and deletes nothing
(state-and-use-cases.md §19b). Schema upgrade is `alembic upgrade head`; backups are
the environment's job.

## 17. Knowledge lifecycle

Facts belong to a user and live in PostgreSQL. Each fact mutation is one transaction
covering fact rows, bindings, the fact-store version, and fact events.

Fact statuses are `pending`, `canonical`, and `deleted`:

- **Create.** New facts are `pending` with a generated ID. `en` rendering is required,
  `he` optional.
- **Confirm.** `pending -> canonical` on explicit confirmation.
- **Edit.** *Not built:* editing a fact in place. Today a correction is a new
  fact with `replaces`; confirming it raises `FACT_SUPERSEDED` on documents using the
  original.
- **Delete.** Confirmed soft delete, allowed even when in use; affected documents
  report `FACT_DELETED_REQUIRES_RESOLUTION`. Submissions are unaffected.
- **Attach.** Adds a canonical fact to a Profile section's pool, optionally pinned.
- **Confirm and use.** Confirms and attaches in one command; the next draft can use it.
- **From a claim.** Creates a pending fact from a claim's exact text.

A fact change moves the basis of documents that use it; a change during a running
analysis fails it with `SOURCE_CHANGED`.

## 18. Operations and failure behavior

`analyze_job`, `create_draft`, `regenerate_section`, `regenerate_claim`, and
`render_document` run as Operations in the worker. Everything else is synchronous.

A failed Operation carries a structured reason code the UI explains. The UI polls and
shows the backend's status and phase.

Queued cancellation is immediate; running cancellation is best-effort and prevents
activation. Retry creates a new Operation with the same model and effort. Operations
are never retried automatically. Details: state-and-use-cases.md §11, §19;
architecture.md §10.

## 19. API and UX contracts

The API is `/api/v1`; `openapi/openapi.json` lists the routes. Async work returns `202`
with the Operation to poll.

The document is at `/applications/{id}/document` with `document_hash` as ETag. Autosave
uses `If-Match`; other document actions send `expected_document_hash`. A mismatch is
`409`, a failed precondition `412`, an oversized body `413`. Errors are Problem Details
with a stable `code`. A failed check is a normal result, not an HTTP error. Full table:
state-and-use-cases.md §22.

## 20. Delivery status

- **Built:** the full workflow from intake through submission and tracking; AI
  analysis and drafting with writer/reviewer; rejected-wording guidance; check →
  approve → render in the Web client; user accounts and per-user isolation.
- **Not built:** hosted deployment (public origin, Host allowlist, HSTS) and editing a
  fact in place.

## 21. Changing this document

This document describes current behavior. Change it together with the code it
describes.

## 22. Accounts and isolation

Commands and routes: state-and-use-cases.md §23. Mechanisms: architecture.md §18.

**Isolation.** A user reaches only their own records, checked by the backend. Another
user's record answers exactly like a missing one (`404`) for every read, write, delete,
download, preview, and Operation. Lists, counts, duplicate detection, and idempotency
never cross users.

**Ownership.** A user owns their Applications, facts, fact events, CandidateContext,
Profile binding, settings, and sessions. Everything else belongs to an Application and
through it to its user. The worker runs each Operation as its Application's owner.

**Accounts.** The operator creates users from the command line and imports their
initial facts; there is no self sign-up. Emails are unique and normalized; passwords
are stored only as a memory-hard hash. Users can sign in, sign out, sign out
everywhere, and change their password, which ends other sessions. The operator resets
forgotten passwords.

**Sessions** expire, can be revoked, and are carried only in an `HttpOnly`, `Secure`,
`SameSite=Lax` cookie. No valid session is `401`, and the client returns to sign-in.

**Sign-in** gives one error for any failure, is rate limited with a temporary throttle,
and never logs passwords or session secrets.

**Not included:** account deletion, per-user AI quota, worker fairness between users,
and account-event audit.
