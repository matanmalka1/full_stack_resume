# CV Application Product Specification

Status: **Binding.** Describes the product as implemented (2026-09-29), including the
single-document model ([`../decisions/single-document-model.md`](../decisions/single-document-model.md)).
Anything designed but not built — today, accounts and isolation (§22) — is marked
*designed, not built* where it appears, and listed in §20.

Section numbers are cited from code, tests, and other documents; keep them stable.

## תקציר מנהלים

כלי שמתאים קורות חיים למשרה, קושר כל טענה לעובדות הקנוניות של המועמד, ומפיק PDF קריא
לאדם ול־ATS. כל משתמש הוא מועמד אחד ורואה רק את המידע שלו (§22 — מאופיין, טרם מומש;
היום הכלי מקומי למועמד יחיד וללא הזדהות).

הזרימה המרכזית:

`Create -> Analyze -> Draft -> Edit -> Check -> Approve -> Render -> Ready -> Submit`

יצירת ניתוח משרה מחייבת ספק AI. מהרגע שקיים ניתוח, כל המסלול עד Ready עובד בלי
מפתח API. Fit, פערים ובעיות ניתוח הם אבחון גלוי ואינם חוסמים; מה שחוסם הוא תוכן לא
נתמך, עובדה תלויה שממתינה לאישור או נמחקה, ובדיקה שנכשלה.

לכל Application יש מסמך קורות חיים אחד משתנה (CVDocument). אישור ו־Ready אינם
גרסאות מוקפאות אלא חותמות על ה־basis הנוכחי של המסמך — התוכן שלו והעובדות שהוא תלוי
בהן — ונגזרים מחדש בכל קריאה. עריכה אחרי אישור מותרת תמיד ומחזירה את המסמך לטיוטה.
מה שנשמר לתמיד הוא מה שנקלט או יצא מהמערכת: נוסח המשרה, הניתוחים, תשובות הספק,
ומה שנשלח בפועל (Submission).

AI מציע — ניתוח, בחירה וניסוח — תחת חוזים מובנים. הוא אינו מקור אמת ואינו כותב
state בעצמו. עובדות קנוניות, מדיניות דטרמיניסטית ו־validation נשארים סמכותיים.

## 1. Authority and interpretation

Authority is ordered as follows:

1. This specification: product semantics, scope, safety rules, and observable behavior.
2. [`state-and-use-cases.md`](state-and-use-cases.md): state values, commands, queries,
   preconditions, error codes, and HTTP mapping.
3. [`architecture.md`](architecture.md): layers, storage, transactions, the Operation
   runner, and runtime.
4. [`test-and-acceptance-plan.md`](test-and-acceptance-plan.md): evidence and release
   matrix.

Where a lower document owns a mechanism, this one states the rule and links to it rather
than restating it. Normative terms (**must**, **must not**, **may**) are intentional.
Internal implementation may change when observable behavior and every invariant stay the
same. A semantic change or a scope expansion needs approval.

## 2. Product goal

### Approved tailoring direction

Development and sales are equal tailoring targets. Wording may rephrase, shorten, and
combine canonical facts without changing their meaning. Every claim keeps its source
links; dates, numbers, historical roles, and experience levels are checked separately.
Semantic review is assistance, not proof.

New wording is accepted without claim-by-claim user confirmation when every hard check
passes, the semantic review accounts for every factual assertion and finds support, and
no contradiction or unresolved uncertainty remains. Final CV approval stays explicit.
This is a policy for accepting reviewed evidence, not a claim that AI proves meaning.
The acceptance rule is §10.1; the reasoning and rejected alternatives are in
[`../tailoring-decisions.md`](../tailoring-decisions.md) (D1).

### Semantic analysis authority

Creating a JobAnalysis requires the configured AI provider. The provider proposes
requirement extraction and interpretation, importance, evidence-linked coverage,
shortfall severity, and the Track/Profile/Emphasis/language classification, from the
exact job text (named by its hash) and the supplied canonical candidate facts.

Deterministic policy stays authoritative over everything it can check itself: locating
each quoted requirement in the exact job text, canonical-fact eligibility, requirement
identity, structural completeness, numeric and compositional consistency, boundary-fact
applicability, Profile legality, Fit, review routing, provenance, activation, and every
later validation and approval boundary. A check may narrow a proposal; it never widens
one.

A canonical fact ID proves that the fact exists, not that it satisfies a requirement.
Positive coverage must keep inspectable evidence. What cannot be established stays
explicit (`unknown`) rather than being turned into matched or unsupported. The closed
concept vocabulary in `config/requirements.json` does not decide coverage; it states
boundary applicability and scale ordering, and both only lower a verdict.

There is no rules-based analysis and no rules-based drafting. Without a provider the
application cannot create a new JobAnalysis or draft a document's content, and a
provider failure never triggers a silent fallback; the UI offers configuration or retry.
Everything downstream of existing content — editing, checking, approval, rendering,
submission, export, and recruitment tracking — works with no provider.

Which canonical facts answer the job is also AI's proposal: `draft_resume` chooses them
from each Profile section's pool while it words them (§10). The engine keeps the checks
that stop an invented fact — canonical, in the section's pool, rendered in the document
language, structurally placed — and treats section budgets, tags, per-role minimums, and
Profile pins as guidance, never as refusals (`docs/decisions/ai-owned-selection.md`).

A matching correction that changes requirement meaning or classification, Emphasis
included, creates a new immutable JobAnalysis (§9).

### Current product contract

> A signed-in user — one candidate — can create a job application, analyze the job, produce and edit a
> fact-linked CV, check and explicitly approve its exact current content, render a valid
> ATS-readable PDF, understand every blocker and available action, record what was sent,
> and track the recruitment process — through the Web client, backed by one application
> layer — and can never reach another user's data (§22).

The Web UI must not require the user to know entity IDs, hashes, filesystem paths,
database details, or architecture. Those stay available in provenance views.

## 3. Product boundaries

- One candidate per user. Each user's `CandidateContext` supplies candidate-specific
  policy; the domain hardcodes no candidate name, filename, or identity. There is no
  candidate selector, candidate CRUD, or multi-candidate UI.
- Facts, CandidateContext, and each user's Profile binding (section pools, pins,
  headlines, omitted roles) are per-user state in PostgreSQL (§17, §22). Profile
  templates, emphasis policy, prompts, task contracts, requirement
  concepts, and rendering rules stay version-controlled files under the project root
  (`profiles/`, `config/`, `ai/`, `rendering/`) and are their own source of truth.
  *Designed, not built:* today facts, CandidateContext, and whole Profiles are files
  under `base/` and `profiles/`.
- React is the product interface. FastAPI is the only user-facing adapter; React
  reaches the system through it and nowhere else. The worker is an internal execution
  host for Operations, not a second client. A second user-facing surface for a use-case
  the API already owns is not added.
- The system is a hosted service: two processes (API and worker) over one PostgreSQL
  database (architecture.md §3.5), reached over HTTPS in production, with
  authentication always on (§22). *Designed, not built:* today it binds to loopback with
  no authentication.
- macOS is the official target. Portable code is preferred; Windows and Linux do not
  block release.
- The UI supports current Chrome/Chromium only. PDFs always render with
  Playwright-managed Chromium.

## 4. Scope

The product includes:

- A Hebrew, RTL, desktop-first Web UI with basic responsive behavior, a persistent shell
  with quick application switching, and light/dark/system theming.
- Job intake from company, target role, and pasted job text, with an optional
  provenance URL and a browser-read `.txt` convenience input; a browser-local recovery
  copy of the unsent form.
- Duplicate warnings from identical URL, identical normalized text, and a company/title
  heuristic, with an explicit acknowledgement step (§8).
- The job text as an editable field of the Application, edited in place when the
  posting changes and locked by the first Submission (§8).
- Provider-backed JobAnalysis with requirements, coverage, gaps, Fit, and analysis
  issues shown as diagnostics; a matching-configuration form for Track, Profile,
  language, and Emphasis.
- Exactly one mutable CVDocument per Application: AI drafting that chooses and words
  the facts, a structured section/claim editor
  with autosave, claim reordering within a section, session undo/redo, targeted section
  and claim regeneration, semantic review of a pending line as written, and isolated
  HTML and stamped draft-PDF previews.
- Explicit content check, explicit approval of the exact current content, rendering with
  browser/PDF/ATS validation, and a derived Ready state.
- A candidate-facts surface ("מאגר העובדות"): list and inspect facts and their history,
  create pending facts (including corrections that `replaces` a canonical fact),
  confirm to canonical, delete, and attach to existing Profile sections. Contextual fact
  resolution from the editor: create a fact from a claim and `Confirm and use`.
- A Dashboard (application list) with search, filters, presets, facets, and sorting;
  Application Detail with preparation state, blockers, next action, notes, unified
  timeline, and submissions.
- Recruitment status transitions, reasoned corrections, one next action with an overdue
  warning, internal and external submissions, close, and soft delete.
- Recruiter-facing PDF download and a human-readable provenance Markdown export of the
  current document.
- Persisted, cancellable, retryable Operations for AI work and rendering.
- Safe Settings (§15), a health endpoint, and read-only maintenance: reconciliation and
  orphan inspection (§16).

## 5. Explicit non-goals

- More than one candidate per user, or candidate administration.
- Roles, permissions, RBAC, organizations, teams, sharing between users, or an admin UI.
- Self sign-up, email verification, password reset by email, and email change. Users are
  created by the operator (§22).
- SSO, MFA, or social login (Google, Microsoft, or any other identity provider).
- A mode without authentication, or any setting that disables it (§22).
- Sync.
- Additional structured-state databases, an ORM, or storage abstractions beyond
  PostgreSQL/SQLAlchemy Core and the local and S3-compatible object stores.
- Automatic job extraction from URLs, LinkedIn, or JS-heavy sites; job-description PDF
  parsing; arbitrary file uploads; general CSV or data import.
- A rules-based analysis, additional AI providers, a provider selector, arbitrary model
  IDs, per-operation model overrides beyond the allowlist, or arbitrary user prompts.
- Cover letters, LinkedIn messages, recruiter emails, or any other document type.
- AI-generated decision explanations.
- Autonomous AI extraction or linking of edited claims. Review of wording against
  explicitly linked canonical facts is in scope (§10.1); review never creates facts or
  reaches facts outside the allowed pool.
- A general Knowledge Manager, or Web editing of Profiles, policies, prompts, taxonomies,
  or rules. The candidate-facts surface edits fact lifecycle only.
- Editing a canonical fact in place, or archive, withdrawal, retirement, or
  known-incorrect fact transitions (§17).
- A WYSIWYG editor, section reordering (section order is Profile policy), or
  drag-and-drop.
- Revision history, approval history, or version comparison of the CV document. The
  history of what was sent is the list of Submissions.
- Mobile-first flows or a full internationalization framework.
- Notifications, calendar integration, recurring reminders, follow-up automation.
- Charts, advanced analytics, or Web CSV export.
- WebSocket or SSE progress; automatic application or schema updates; built-in backup
  and restore.

No non-goal enters the product as a small convenience without an explicit scope
decision.

## 6. Core invariants

1. An `Application` is the container for one target job and its history.
2. Each user is exactly one candidate. Every record belongs to exactly one user,
   directly (a root) or through its Application; no command or query reaches a record
   of another user, and such a record is indistinguishable from one that does not exist
   (§22). *Designed, not built:* today the system represents one candidate and
   Application rows carry no owner.
3. `CVDocument` is the only mutable resume document. Exactly one exists per Application
   once its first analysis activates.
4. JobAnalysis, provider-response Artifact, Submission, recruitment/audit/
   fact events, and terminal Operation records are immutable, and an Application's job
   text is locked once it has a Submission. Database triggers enforce it, not
   convention.
5. Editing an approved or Ready document is always allowed. It changes the basis, so the
   document reads as a draft again; no command reopens it and no history record is
   created.
6. Approval and Ready are not stored entities. They are derived on every read by
   comparing the stored `approved_basis` and `rendered_basis` with the current `basis`
   (state-and-use-cases.md §3–§4).
7. The basis covers the document's content and analysis pin
   (`document_hash`) and the current state of every fact it depends on (`facts_hash`).
   A change to any of them outdates every stamp at once; nothing invalidates a stamp by
   writing.
8. Approval requires a passing deterministic content check of the exact current basis.
   `approve_document` runs that check and approves in one action.
9. Unsupported, pending, unlinked, strengthened, or unreviewed claims may be saved but
   block approval.
10. A valid fact ID does not prove that wording is supported. Wording is supported only
    by a deterministic proof or complete eligible reviewed evidence (§10.1).
11. AI outputs are Proposals. Schema validation, deterministic policy, and an
    application commit decide what becomes state.
12. AI failure never triggers a silent fallback, and analysis and drafting have no
    rules-based form to fall back to. The user may retry. A proposed line withheld under
    §10.1 is not a fallback: it keeps the wording it already held, and the Operation
    reports it.
13. Provider, cancelled, or stale output never becomes current state. It becomes current
    only through a successful commit against its original preconditions; every provider
    call stays in the immutable AI call log either way.
14. Preparation and recruitment are independent lifecycles.
15. Recruitment history is append-only. Corrections add events and never rewrite past
    ones.
16. A Submission's copied content and files are never overwritten, relocated, or
    deleted. The document keeps changing after submission; the Submission does not.
17. No mutable content has two sources of truth.
18. Nothing in the system deletes an immutable payload.
19. Normal queries never expose a partially committed cross-store mutation.
20. `delete_application` and `delete_fact` are soft deletes: a terminal disposition on a
    mutable row, audited like any transition. They remove no row, rewrite no prior
    content, and touch no immutable table. A deleted Application or fact leaves default
    listings but stays reachable by ID, with every record produced from it preserved.
21. API and worker concurrency stays correct through the document hash, optimistic
    versions, atomic PostgreSQL claims guarded by unique indexes, idempotency keys, and
    commit-time precondition checks.
22. A fresh installation starts with an empty database — no users — and proves itself
    through its own workflow.
23. Commands name their sources; only a query may resolve "latest".

## 7. Candidate and application behavior

Each user has one CandidateContext (per-user state, §22; today `base/candidate.json`).
It points to the user's canonical name and contact fact IDs (with track-specific contacts, such as GitHub for development) and supplies
filename language, locale, timezone, and link schemes. Names and contacts stay canonical
facts, not duplicated metadata.

The recruiter-facing filename uses the candidate name in the configured filename
language (English by default), including for a Hebrew CV. Renderers and filename policy
receive CandidateContext explicitly and contain no candidate literal.

Knowledge, artifacts, temporary files, and logs live at fixed directories below the
installed project root (once accounts ship, only policy files remain there; §22). The root is not selectable (architecture.md §4).

## 8. Job intake and job text

The intake form requires company, target role, and the full job text; the source URL is
optional. Notes belong to Application Detail, not to the intake form.

The Web form keeps an exact browser-local recovery copy that survives a reload or a
later session. Duplicate prompts, network failures, and refusals never discard entered
values. A storage failure is visible and never blocks editing or submission. A
successful creation clears only the copy it created from. The copy is not the
Application's job text and carries no authority.

`create_application` is synchronous and deterministic and never calls AI. It stores the
exact text received on the Application, without line-ending normalization, with a hash
over that representation (`job_text_hash`) and a separate normalized hash for
deduplication. A browser-read `.txt`
file only fills the text area; nothing is uploaded. The URL is provenance only, is never
fetched, must be `http(s)`, and is bounded in length and control characters.

Duplicate detection runs before creation for UX and again inside the command. Deleted
Applications are not matched. Unacknowledged matches refuse the first attempt
(`DUPLICATE_ACKNOWLEDGEMENT_REQUIRED`, 412); resending with acknowledgement creates the
Application. A duplicate is never a dead end: the user may open the existing Application
instead.

After a successful Web creation the client queues `analyze_job` for the new job text. If
queueing fails, the created Application is still the destination and Analyze stays
available; creation is never retried.

A changed posting is an edit of the job text in place (`update_job_text`); there is no
version history and no comparison view (`docs/decisions/editable-job-text.md`). The
edit names the text it replaces by hash. Analyses of the earlier text stay on record
but are no longer of the Application's text: Analyze becomes available, the document
reads `DOCUMENT_ON_OLDER_ANALYSIS`, and nothing changes the document until the user
runs `build_from_analysis` against a newer analysis. A document whose analysis read the
earlier text cannot be drafted, since that text is gone.

The first Submission, internal or external, locks the job text: the edit is refused
from then on, so a Submission's `job_text_hash` always names text the Application still
holds.

## 9. Analysis and review

JobAnalysis owns classification, normalized requirements, coverage, analysis issues,
and source coverage. Fit and gaps are projections of its requirements. Each analysis is
immutable and is its own version.

The first successful `analyze_job` for an Application creates the JobAnalysis and, in
the same transaction, the CVDocument pinned to it with no content. A later analysis
never touches the document; it is reported as the `DOCUMENT_ON_OLDER_ANALYSIS` warning
until the user runs `build_from_analysis`, which re-pins the document and clears its
content and every stamp.

The document holds no selection. The facts it uses are the facts its content links;
they are chosen when the content is drafted (§10) and changed by editing it.

The matching-configuration form (`apply_analysis_decisions`) changes classification
only: a Track, Profile, language, or Emphasis change creates one new immutable
JobAnalysis without calling the provider.

Fit, hard gaps, low Fit, and analysis issues are diagnostics. They stay visible and
never require acknowledgement or block an action. An uncertain requirement stays
`unknown`; missing evidence is never shown as missing experience.

Review reasons are reserved for the integrity of the document's own dependencies: a
dependent fact that is pending or deleted (state-and-use-cases.md §7). They block
approve, render, and submit, and are resolved by confirming, editing, or regenerating.

When the user has turned on automatic generation (off by default), the Web client
queues a draft right after the analysis that created the document activates, provided
the projection shows no review reason, no live Operation, and `create_draft` available.
This is a client convenience over the same command; it grants no authority.

## 10. Drafting and editing

The structured DraftDocument in `cv_documents.content` is the only source of truth for
content. Markdown and HTML are projections.

`create_draft` runs as an AI Operation while the document has no content; there is no
rules-based drafting lane. The engine sends `draft_resume` each Profile section's
pool — every canonical fact with its rendering in the document language — the structural
facts that are always present, and the section's guidance: claim budget, per-role
minimums and ceiling, required and preferred tags, tag weights, and Profile pins.
`draft_resume` chooses the facts per section and words them. The engine narrows the
answer and never widens it: a fact outside the section's pool or not canonical is
refused, and a chosen fact without a rendering in the document language fails the draft
(`MISSING_FACT_RENDERING`). Guidance is never enforced. The engine lays the chosen facts
out in pool order, so every role keeps its title, dates, and bullets together, and the
wording activates only through §10.1.

The editor works with sections and claims. Each claim shows its text, linked facts,
status, warnings, and edit, regenerate, and remove controls. Section order is Profile
policy and never moves; claims may be reordered within a section. Undo and redo are a
client-side editing history saved through the same autosave. Headline and contacts are
structural: the headline is not a factual claim and is accepted only when it is one of
the Profile's safe headlines.

Any section claim may be removed; the fact it linked simply stops being used. There
is no separate fact selection to change.

Free-text edits are always saved, even when unsupported. They become pending or
unlinked claims, are shown as unsafe, and block approval until they are supported
through a deterministic proof or §10.1, resolved through the fact lifecycle (§17), or
removed. Unlinked text needs explicit fact links before semantic review. A provider can
never turn edited text into a fact or authorize its own wording.

`regenerate_section` and `regenerate_claim` rewrite a named section or claim through the
same writer-then-reviewer path. `regenerate_claim` with `keep_text` sends a pending,
fact-linked line to review exactly as written: no writer runs. A writing Operation
reviews only the lines it wrote.

For reviewed wording, the document read exposes a safe explanation: review policy
version and assertion-to-source excerpts. Provider artifact IDs and input hashes stay
internal. The editor labels it as semantic review, not proof, and warns that changing
the wording invalidates it.

Autosave uses debounce and blur with the document hash as ETag. A stale save is a
conflict that overwrites nothing; the UI shows the user's text and the current text for
an explicit choice, with no automatic merge.

The HTML preview renders the current content server-side through the render composition
into an isolated iframe, marked as a draft. A stamped draft PDF is available on demand
through the same composition and browser. Neither needs approval, stores anything, or
writes any document field, Artifact, or Operation. Seeing the layout never requires
approving.

### 10.1 Reviewed wording

Wording may paraphrase, shorten, or combine information from several canonical facts
without changing meaning. Each fact keeps its identity. A combined sentence must not
invent a relationship, causal claim, employer, time period, or experience level.

Canonical, extractive, and presentation proofs are deterministic and need no review. New
wording needs every hard check to pass plus a separate semantic review
(`assess_claim_support`) against the exact sources and document context. The review must
account for every factual assertion, including protected values and attribution. A fact
ID, matching words, an aggregate confidence score, or the absence of a detected error is
not evidence.

Acceptance requires all hard checks, complete positive review evidence, and no known
contradiction or unresolved uncertainty. Accepted wording needs no individual user
confirmation, and its provenance says semantic review, not deterministic proof. A known
contradiction overrides positive review. Unsupported or strengthened wording is a
blocker. General CV approval resolves none of these.

In the implemented lifecycle, the writer and the reviewer run inside one Operation, and
their answer is judged line by line. A proposed line becomes state only through a hard
check it passes or a fully `supported`, attested review. Any other line is *withheld*: it
keeps exactly the wording, links and proof it held before the Operation (for a first
draft, its frame line composed from canonical facts), and none of its proposed content
reaches the document. The lines that passed are written, and the Operation succeeds and
lists every withheld line. A writer line refused before review (a fact outside the task's
pool, no linked fact, wording the edit path rejects) is withheld the same way; a claim ID
the document does not hold names no line and is ignored. Only when every line the answer
named is withheld does the Operation fail, with `unsupported` (`CLAIM_REVIEW_UNSUPPORTED`),
then `uncertain` (`CLAIM_REVIEW_UNCERTAIN`), then `INVALID_OUTPUT` as its code: both
provider calls stay in the AI call log, the document is unchanged, and retry or
correction is offered. A single-line task (`regenerate_claim`, or a review of the user's
own wording) therefore succeeds or fails whole. Review failure, cancellation, invalid
output, missing assertion coverage, or stale evidence never makes wording eligible.

Failed semantic reviews and withheld lines expose a focused clarification panel: the
rejected sentence,
its section and preceding heading when present, the exact canonical meanings and
renderings read during that review, and the reviewer's explanation when one was
recorded, labeled as the reviewer's reading rather than proof. This context is recorded with the failure, not
reconstructed from the current document or fact store. Older failures without recorded
context retain generic guidance; missing historical content is never invented.

A `supported` answer whose evidence fails the deterministic review check is refused as
invalid output; the same panel shows that line as unattested, with the failed checks in
the reader's words, because the reviewer's own explanation reads as approval.

The panel distinguishes an uncertain verdict from an unsupported one and offers the
existing editor and fact lifecycle as resolution paths. A claim link opens the current
document at that claim if it still exists; the displayed failure context remains
historical. Initial drafting failures return to preparation because no draft activated.
The user may keep the unchanged document, edit or remove a line, retry writing, or
supply new facts through the fact lifecycle. The ordinary validation and approval
boundaries apply to every correction. There is no acknowledgement or human-attestation
override: clarification itself never activates proposed wording or authorizes a claim.

## 11. Validation, approval, rendering, and Ready

Editing runs lightweight claim, structure, and required-field checks. `check_document`
runs the full deterministic content check explicitly; `approve_document` runs the same
check as part of approving. Neither calls AI. Browser, PDF, and ATS checks run inside
`render_document`.

The content check verifies the eligibility and currency of every claim's proof or
review evidence — wording, language, sources and their content, attribution, allowed-fact
scope, and review-policy versions — plus hard rules, section placement, and fact
eligibility. A missing review is never read as success. A failed check is a successful
result with `passed = false` and structured issues; an exception means the validator
could not run. Only the current report is kept, stamped with the basis it was produced
for, and shown as outdated once the basis moves. There is no validation history.

Warnings are visible and never block. Anything that needs a specific decision is a
blocker or review reason, not a warning.

Approval is always an explicit user action. It stamps `approved_basis` and `approved_at`
on the document when the check passes and no blocker or review reason exists. It does
not freeze or copy content. It is refused while a Knowledge mutation is quarantined
(§17). Approving an already-approved basis is a no-op.

Rendering is a separate Operation, available only while the document is approved. It
revalidates against current Knowledge, renders HTML and PDF to a fresh per-attempt
location, and checks geometry, page count, PDF/ATS text, links, direction, and filename
metadata. Only a successful render of the still-approved, unchanged document stamps
`rendered_basis`. A render failure keeps the document approved, is shown with a
structured reason, and never touches the active files.

A document is **Ready** when `approved_basis` and `rendered_basis` both equal the
current basis. Ready is never stored. There is only one document, so there is no
"previous Ready" alongside a newer draft: the document either is Ready for its current
basis or it is not. A newer analysis does not change the document or its state.

A chained check → approve → render flow is permitted as an explicit user instruction,
recorded with `actor_type = user` and the originating client. It never bypasses a
blocker or validation and never approves because an AI Operation completed. No
interface offers it yet; the rule binds whichever one does.

The Ready screen shows the preview, the recruiter-facing PDF download, the content
report, and the document's provenance, and offers editing (which returns the document
to draft) and submission.

## 12. AI behavior

One OpenAI adapter implements the provider-neutral `AIProvider` port, using the
Responses API with strict Structured Outputs. The task contract (`ai/contracts/
task_contracts.json`, with the prompt `ai/prompts/system.md`) defines five tasks:

- `propose_analysis` — requirements with importance, evidence-linked coverage, shortfall
  severity and reason, and the Track/Profile/Emphasis/language classification, as one
  Proposal from one call. Called by the `analyze_job` command.
- `draft_resume` — the facts chosen per section and their wording, for a new draft.
- `regenerate_section`, `regenerate_claim` — targeted rewording.
- `assess_claim_support` — the separate semantic reviewer used by every writing
  Operation. It returns evidence proposals only.

The analysis task never decides Fit, review routing, approval, or activation (§2).

**Tolerant reading.** A flawed part of a reading narrows that part and is recorded as an
analysis issue; the rest stands. Only an unparseable response fails the Operation. The
engine locates each quotation in the job text itself; a requirement it cannot locate is
kept and marked unverified, an ambiguous quotation falls to `unknown`, and positive
coverage resting on an unresolved citation falls to `unknown`. Uncertainty is recorded as
`unknown`, never as absence of experience.

**Coverage and shortfall.** `partial` means canonical facts answer only part of a
requirement; it does not by itself say the uncovered part is material. A mandatory
requirement is a hard gap when it is `unsupported`, or `partial` with shortfall severity
`material`; a `minor` or `unknown` shortfall is a warning. The provider proposes severity
and reason; deterministic policy normalizes inconsistent combinations and stays
authoritative over numeric and boundary checks. Qualitative wording (strong, deep,
large-scale, maintainable) is assessed from the breadth, complexity, responsibility, and
outcomes in the facts; a fact need not repeat the modifier or state a proficiency level,
and their absence alone is not a shortfall. When the facts do not permit a
determination, the result is `unknown`, not an invented gap. Fit arithmetic is
state-and-use-cases.md §13.

**Writer and reviewer.** The reviewer runs as a separate call and never uses the
writer's self-assessment as evidence. Separate calls do not guarantee independent
judgment. Application policy, not the provider, decides whether evidence satisfies
§10.1.

**Context.** Calls are stateless. Each task receives only what it needs: the
job text, the canonical facts for evidence matching or the facts permitted per
section, the Profile catalogue, and task policy. Historical artifacts are not sent. The
UI states that job text and canonical facts are sent when AI is used; there is no
per-call consent dialog.

**Configuration.** `OPENAI_API_KEY` is environment-only: `.env` and project config cannot
enable it, and it is never stored in PostgreSQL, sent to React, or logged. Settings
report only whether a provider is configured. Models come from a backend allowlist,
reasoning effort is `low`/`medium`/`high`, and both are frozen into each Operation when
it is queued, so a later settings change cannot alter queued work. There is no dynamic
model discovery.

**Provenance.** Every provider call attempt - successful, refused, failed, or without
an answer - is appended to the AI call log as soon as it ends: its sanitized response
in canonical JSON form and that form's hash, response ID, model, outcome, error type
and code, usage (cached input and cache-write input separately), latency, hashes, the
task-contract, schema and prompt versions and hashes, the dated USD price snapshot, and
derived cost. The log is append-only. The request payload is not kept; its hash is.
Secrets and hidden reasoning are never kept. A usage or cost the provider did not
report is unknown, never zero, and an Operation's totals are unknown when any of its
attempts' are - except an attempt proven never delivered, which used nothing. A billing
refusal (`PROVIDER_QUOTA_EXHAUSTED`) is reported apart from a rate limit, because the
user fixes it in the provider account rather than by waiting. A provider call is retried at most once, per call, only where the
second attempt cannot duplicate a processed request or the provider asks for it
(architecture.md §11); a failure that may have reached the provider is never retried
automatically.

**Untrusted input.** Job text and user content are data. They may shape proposed
content but never policy, allowed facts, validation, approval, or output schemas.
Injected instructions in a posting are not requirements: the same posting with and
without them must yield the same actionable requirements, coverage, gaps, Fit, and
review decisions. An exact quotation proves presence, not legitimate meaning. Mock tests
prove contract enforcement; model behavior needs live evaluation and is not a guarantee
of injection resistance.

## 13. Preparation and recruitment

Preparation and recruitment are separate views of one Application.

`preparation_state` (`needs_analysis`, `ready_to_draft`, `draft_in_progress`,
`approved`, `ready`) is the one document state a client reads. Recruitment status
describes the application after it is saved or sent. Values and transitions belong to
state-and-use-cases.md §4 and §10. Preparation commands never change recruitment status,
and `closed` is archival rather than an outcome.

Every Application projection — detail and list row — carries the preparation state,
content-check state, review reasons, warnings, active and latest Operation, the
document's ID, hash, and analysis pin, available actions, blocked actions with their
reason codes, and a nullable recommended action, computed from one consistent read
(state-and-use-cases.md §9). The backend owns action policy; React does not implement a
second state machine.

## 14. Recruitment tracking

The Dashboard is a table with search, stage and status filters, presets (needs
attention, ready to send, active interviews), facet counts, sorting, and paging. Each
row shows preparation and recruitment state, last activity, next action and date, live
Operation, and warnings. There are no charts.

Application Detail shows the header, status and next action, notes, current preparation
and its blockers, one unified timeline, the document and its provenance, submissions,
and navigation to the editor.

`submit_application` records a send that already happened. It requires the document to
be Ready with both files present and no review reason. It copies the exact content and
the rendered HTML and PDF to submission-owned storage with a SHA-256 per file, creates an
immutable Submission, moves `saved -> applied` when needed, and appends status and audit
events in one transaction. A document on an older analysis is a non-blocking warning.
Multiple submissions are allowed, add no further transition, and never change the
document.

`record_external_submission` records a send made outside the system: immutable, with no
content or files, and the same `saved -> applied` rule.

`saved -> applied` belongs to submission only. Other transitions follow the allowed
graph. A wrong status is fixed by an explicit correction event that names the corrected
event and carries a mandatory reason. The current status is a transactionally
consistent projection; events are audit history, not event sourcing.

One next action and date may be active; each change appends an event. Overdue is a
computed warning while the date is past and the status is not terminal. There are no
notifications.

There is no hard delete. An Application may be closed, or soft-deleted (invariant 20)
from any status; deletion is orthogonal to recruitment status and has no undo.

Audit identity is `actor_type` (`user` | `system`) and `client` (`web` | `worker`),
and the acting user is the owner of the record audited: a user acts only on their own
records, and the worker acts for the owner of the Operation it runs (§22). The UI may
show "You" for `actor_type = user`; client identity belongs to provenance. Account
events have their own audit (§22).

## 15. Runtime and security

The product serves UI and API from one origin. Every route except sign-in and health
requires a session (§22). It validates `Origin` on every
mutation, accepts only its configured hosts, and uses an explicit CORS list with no
wildcard (architecture.md §14). *Designed, not built:* today it binds to loopback and has
no authentication.

Safe settings are per-user, server-owned, and optimistic (a stale write is a conflict the user
resolves; nothing is overwritten automatically):

- `auto_generate_when_review_not_required` (§9), off by default;
- there is no AI switch: AI is available exactly when a provider is configured
  (`provider_configured`, read-only), and the Web client disables AI actions without one;
- `default_ai_model` and `default_reasoning_effort`, from closed allowlists;
- UI preferences: `ui_theme` (`system` default, `light`, `dark`), `ui_density`,
  `ui_text_size`. The server is authoritative for theme; a local cache is for startup
  display only.

Per-task overrides, timezone, arbitrary model IDs, and secrets are never writable.

## 16. Storage, provenance, and retention

Storage layout is architecture.md §6. Storage keys and local paths are never API inputs.
Downloads are addressed by ID, verify the registered hash, and use a friendly filename.

**What a Submission records.** An internal Submission stores the document's exact
`content`, `document_hash`, the `job_text_hash` of the Application's job text when it was
sent (which the Submission locks), the copied
HTML and PDF with their SHA-256, `submitted_at`, and user metadata. The content itself
carries its binding (Application, the job text hash its analysis read, analysis),
Track/Profile/Emphasis, language,
each claim's fact links and evidence, and the coarse fact-store
version. The Submission does **not** store `facts_hash`, the CandidateContext version,
or policy versions; those are not recoverable for it later, and no field may claim them.

**The document's own provenance.** `built_with` (Profile version) drives the
`PROFILE_CHANGED` warning. Approval and rendering always
validate against current Knowledge rather than trusting `built_with`. `facts_hash` covers
only the facts the document depends on, so an unrelated fact change does not move its
basis.

**Retention.** Nothing deletes an immutable record: Submission files, the job text a
Submission locked, and the AI call log stay forever. Replaced document content is not archived —
`build_from_analysis` and editing overwrite it — and superseded rendered files are
working outputs deleted best-effort. Only a Submission keeps what was sent.

**Maintenance.** Maintenance is an operator task, not a user one: once accounts ship,
reconciliation and orphan inspection span every user and move from the API to the
operator CLI (§22). Reconciliation checks every registered payload against its hash, every
logged AI call's sanitized response against its hash, and the fact lifecycle against its
trail, reports each, and repairs nothing. Orphan
inspection lists unreferenced payloads older than one hour and deletes nothing
(state-and-use-cases.md §19b). Schema upgrade is the explicit `alembic upgrade head`;
PostgreSQL and bucket backup are the environment's responsibility.

## 17. Knowledge lifecycle

*Designed, not built (§22):* facts belong to a user and live in PostgreSQL. A fact
mutation is then one database transaction — fact row and fact events commit
together — and the mutation journal, its recovery, and
quarantine are retired. Hand edits to Knowledge files are no longer an input; `base/`
is import input for an existing installation only. The lifecycle rules below (statuses,
create, confirm, delete, attach, confirm and use, from a claim) are unchanged. Until
then, the implemented mechanism is:

Knowledge stays file-based and version-controlled. A fact mutation from the Web runs:

```text
React -> FastAPI -> FactLifecycleService -> validate/stage -> PREPARED journal entry
      -> replace file -> fact events + COMMITTED, one transaction
```

File work runs outside database scopes. The journal and audit never replace the files as
the source of truth (architecture.md §7.2). The application never runs a Git commit.

Fact statuses are `pending`, `canonical`, and `deleted`:

- **Create.** New facts enter `pending` with a generated UUIDv4 ID; the UI never creates
  IDs, and existing semantic IDs stay valid. `en` rendering is required, `he` optional;
  meaning, tags, provenance, and dates are explicit input. A correction is a new fact
  carrying `replaces`; the original is never edited.
- **Confirm.** `pending -> canonical` on one explicit confirmation. Confirming a
  replacement marks the original superseded (`FACT_SUPERSEDED` warning); it rewrites
  neither the original nor any Submission.
- **Delete.** An explicitly confirmed, one-way soft delete from `pending` or `canonical`.
  Always allowed, even for a fact in use; it writes nothing to any document, whose basis
  moves and which then reports `FACT_DELETED_REQUIRES_RESOLUTION`. Submissions are
  unaffected.
- **Attach.** Offers a canonical fact to an existing Profile section's pool, optionally
  pinned. It changes no Profile structure and grants no Profile editing.
- **Confirm and use.** One journaled command that confirms the fact and attaches it to
  the named Profile section, or fails as a whole. It writes no document; the next draft
  of that Application's document can choose the fact.
- **From a claim.** Copies the claim's exact text as a rendering without AI rewriting.
  The claim is not authorized until the fact is canonical and in its section's pool.

There are no archive, withdrawal, retirement, or known-incorrect transitions, and no
client may present them.

An unrecoverable journal entry is quarantined. While any is, every fact mutation and
every approval is refused; reads, history, export, and recruitment tracking continue.

Hand edits to the Knowledge files are supported. Commands re-read or re-hash their
dependencies rather than trusting a cache; a dependent change moves the document's
basis, and a change under a running analysis fails it with `SOURCE_CHANGED`. A changed
fact is never silently reloaded into an open editor form.

## 18. Operations and failure behavior

AI tasks (`analyze_job`, `create_draft`, `regenerate_section`,
`regenerate_claim`) and `render_document` run as persisted Operations in the worker,
never inside an HTTP request.
Saves, matching decisions, `build_from_analysis`, check, approval,
submission, fact commands, and recruitment changes are synchronous.

Status and failure reason are separate, and a failure carries a structured reason in a
closed vocabulary that the UI explains without parsing text. The UI polls and shows the
backend's status, phase, and message; there is no fabricated progress.

Queued cancellation is immediate. Running cancellation is best-effort and prevents
activation; a provider call that already happened stays in the AI call log. Retry
creates a new Operation that references the original and copies its model and effort.
The Operation itself is never retried automatically: one provider call is retried at
most once where it is safe (§12), and a browser that failed to start is started once
more, both only while the Operation is still running, held, and not cancelled. Types, phases, failure codes,
concurrency rules, and idempotency are state-and-use-cases.md §11 and §19 and architecture.md
§10.

## 19. API and UX contracts

The HTTP API is `/api/v1`; `openapi/openapi.json` is the authoritative route inventory.
It exposes use-cases without leaking database or filesystem representations.
Asynchronous work returns `202` with the Operation to poll.

The document lives at `/applications/{id}/document` with `document_hash` as a strong
ETag. Autosave (`PATCH`) uses `If-Match`; every other document action carries
`expected_document_hash` in its body. A mismatch is `409`. A precondition such as a
blocker or review reason is `412`. Errors are Problem Details with a stable machine
`code` and safe context; technical detail stays in logs. A review reason or a failed
check is a successful domain outcome, not an HTTP error. Oversized bodies are `413`.
The full outcome table is state-and-use-cases.md §22.

An application-list export projection (schema `2.0`) exists in the application layer
with no route; Web CSV export is a non-goal (§5).

## 20. Definition of Done and delivery status

The product is Release Ready when a user can go from job intake to a validated Ready
PDF, understand and resolve every blocker, record the submission, and track the
recruitment lifecycle without knowing technical identifiers or architecture — while
preserving every invariant here, including immutable history, unsupported-claim
blocking, concurrency safety, recoverable Operations, and a provider-free path from an
existing analysis through Ready.

State as of this revision (details: `tailoring-decisions.md` §2–§3):

- **Implemented and gated:** the full engine and Web workflow described above, from
  intake through submission and tracking.
- **Implemented, live acceptance incomplete:** AI tailoring (writer/reviewer v1, sectioned
  selection and writer context). The sales sample reached Ready. The development
  sample needed repeated drafting and a content exclusion before its PDF fit the page
  limit. These are live observations, not proof of repeatable quality.
- **Implemented:** focused correction guidance for rejected wording (§10.1) and the Web
  check → explicit approval → automatic render flow (§11). Rejected wording remains
  inactive, with correction through the editor or fact lifecycle.
- Live acceptance and experience measurements are recorded separately in
  `../acceptance/2026-09-29.md`; an unsuccessful run does not constitute acceptance.
- **Approved, not built:** user accounts, per-user isolation, and per-user Knowledge
  (§22). Until they ship, the implementation is the single-candidate, loopback-only,
  unauthenticated tool, and every section marked *designed, not built* describes the
  target. Delivery order: `../decisions/multi-user-accounts.md` §5.

Executable evidence and the release matrix are defined only in
`test-and-acceptance-plan.md`.

## 21. Change and stop conditions

Naming, folder structure, and other internal details that preserve contracts proceed
without approval. Work stops for an unresolved semantic conflict, a scope expansion,
migration or data-loss risk, any path that could let unsupported claims through
approval, a deployment-model change, or any dual-write behavior.

## 22. Accounts and isolation

*Designed, not built.* Why and how an existing installation maps onto it:
[`../decisions/multi-user-accounts.md`](../decisions/multi-user-accounts.md). Commands,
error codes, and routes: state-and-use-cases.md §23. Mechanisms and defaults:
architecture.md §18. Evidence: test-and-acceptance-plan.md §3.11.

**Isolation is the invariant this section exists for.** A user reaches only their own
records, and only through the backend's check; the Web client hiding something is never
the check. Another user's record answers exactly like one that does not exist (`404`),
for every read, write, delete, download, preview, and Operation, including through an
ID taken from a URL or a log. Lists, facets, counts, duplicate detection, and
idempotency never see across users.

**Ownership.** A user owns their Applications, their Knowledge (facts, fact events,
CandidateContext, Profile binding), their settings, and their sessions and account
events. Everything else — job text, analyses, the CVDocument, Operations,
artifacts, Submissions, recruitment and audit events — belongs to an Application and
through it to its user. A canonical fact belongs to a user, not to an Application;
Applications reference facts. The worker runs every Operation as the owner of its
Application and reads only that user's Knowledge.

**Accounts.** There is no self sign-up. The operator creates a user from the command
line with an email and a password, and imports that user's initial facts. The email is
stored normalized and is unique. Passwords are stored only as a memory-hard hash; no
password or session secret is stored or logged in raw form. A user can sign in, sign
out, sign out of every device, change the password (with the current one), and
deactivate the account (with the current password). Changing the password ends every other
session. A forgotten password is reset by the operator, which also ends every session.

**Sessions** expire and can be revoked, and are carried only in an `HttpOnly`,
`Secure`, `SameSite=Lax` cookie; the Web client never holds a token in script-readable
storage. A request with no valid session is `401`, and the Web client then clears its
state and returns to sign-in.

**Sign-in** fails with one answer — the email or password is wrong — whatever the
reason, and is rate limited with a temporary throttle and no permanent lockout. AI
Operations are subject to a per-user quota, because the provider key and its cost are
the operator's.

**Account deactivation** is the only way an account ends: deactivate, revoke every
session, and anonymize the personal data held in mutable fields — the exact list is
state-and-use-cases.md §23. There is no account deletion. Immutable records — Submissions, the job text they locked, the AI call log, audit and fact events
— stay, owned by a user row that no longer identifies anyone and that nobody can sign
in to. A hard delete is not a product capability.

**Audit.** Sign-in, failed sign-in, sign-out, password change and reset, and account
deactivation are recorded as append-only account events, separate from Application
audit, never with a password or a session secret.

**Unchanged.** Every rule in §1–§21 still holds inside one user's data: factual safety,
approval boundaries, immutability, the provider-free path from an existing analysis to
Ready, and the Operation model.
