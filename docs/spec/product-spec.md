# CV Application Product Specification

Status: **Approved for v2.0 implementation**

## תקציר מנהלים

כלי מקומי למועמד יחיד שמתאים קורות חיים למשרה, שומר כל טענה קשורה לעובדות
הקנוניות של המועמד, ומפיק PDF קריא לאדם ול-ATS.

הזרימה המרכזית היא:

`Create -> Analyze -> Review if required -> Draft -> Edit -> Validate -> Approve -> Render -> Ready`

Review הוא שער מבוסס חריגים, לא מסך חובה. המערכת ממשיכה אוטומטית ל-draft כאשר
אין ambiguity מהותית, gap הדורש החלטה, claim לא נתמך או בחירת עובדות לא פתורה.
האישור ב-Web תמיד מפורש. CVDocument הוא מסמך הרזומה המשתנה היחיד לכל Application;
עריכה אחרי אישור או רינדור מותרת ומחזירה אותו ל-draft. רק Submission - מה שנשלח
בפועל, כולל קובצי ה-HTML וה-PDF שהעתיק - הוא immutable.

AI מסווג ומציע ניסוח תחת חוזים מובנים. הוא אינו מקור אמת ואינו יוצר ישויות domain
ישירות. עובדות canonical, policy דטרמיניסטי ו-validation נשארים סמכותיים. לאחר
שקיים JobAnalysis, המסלול עד Ready PDF ממשיך לעבוד ללא API key.

## 1. Authority and interpretation

Authority is ordered as follows:

1. This product specification defines binding product semantics, scope, safety, and
   observable behavior after it is approved.
2. `docs/spec/state-and-use-cases.md` defines the detailed state, command, query, and
   permission contracts consistent with this specification.
3. `docs/spec/architecture.md` defines the technical architecture that implements those
   contracts.
4. The implementation and test plans define execution and evidence.

Normative terms such as **must**, **must not**, **should**, and **may** are intentional.
Internal implementation may change without approval when observable behavior and every
invariant remain unchanged. Semantic changes and scope expansions require approval.

## 2. Product goal

### Approved tailoring direction

The user approved development and sales as equal tailoring targets, with rephrasing,
shortening, and combining information from canonical facts without changing their
meaning. Every claim retains source links; dates, numbers, historical roles, and
experience levels require separate checks. Semantic review is assistance rather than
absolute proof. Unresolved support requires claim-specific clarification; general CV
approval cannot bypass it. New candidate information follows the fact lifecycle,
separately from wording requests.

New wording may proceed without
claim-by-claim user confirmation when hard checks pass, semantic review covers every
factual assertion and finds support, and no contradiction or unresolved uncertainty
remains. Only uncertainty requires focused user clarification. Final CV approval
remains explicit. This is a policy for accepting reviewed evidence, not a claim that
AI proves meaning or cannot miss an error.

Sections 10–12 define the current acceptance contract. Decision history and unresolved
design work are recorded separately in [Tailoring decisions](../tailoring-decisions.md).

### Semantic analysis authority

Job analysis requires an AI provider. The provider proposes requirement
extraction, interpretation, evidence matching, and Track/Profile/Emphasis classification
from the exact JobSnapshot and the supplied canonical candidate facts. Deterministic
policy remains authoritative over source attestation, canonical-fact eligibility,
structural completeness, internally checkable numeric and compositional consistency,
requirement identity, Fit calculation, review routing, provenance, immutable activation,
and every later claim-validation and approval boundary.

A canonical fact ID proves that the fact exists; it does not by itself prove that the
fact semantically satisfies a requirement. Provider self-reports likewise do not prove
source completeness, numeric values, or boundary applicability. Positive coverage must
retain inspectable evidence, and any material condition that cannot be established by
the implemented independent gates remains explicit and reviewable rather than being
silently converted to either matched or unsupported.

Legacy rule gaps and the concept vocabulary do not constrain or merge into AI-mode
coverage. In particular, deterministic rules do not attempt general semantic matching.
Canonical boundary facts remain authoritative, and their applicability must not depend
solely on an optional provider relation or tag. Completeness uses an independently
derived structural denominator; a provider cannot certify its own completeness merely
by returning no unmapped statements.

Without a configured provider, the application cannot create a new JobAnalysis. It may
still use an existing analysis to perform deterministic editing, validation, approval,
rendering, integrity, export, and recruitment workflows whose prerequisites already
exist. Provider failure never triggers a silent rules-based analysis. The UI presents
provider configuration or retry instead of a fabricated semantic result.

A user decision remains required for a material professional choice such as changing the
matching classification or selecting facts. Hard gaps, low Fit and incomplete analysis
are visible diagnostics, not acknowledgement gates. A matching correction that changes
requirement meaning or classification creates a new immutable JobAnalysis and re-derives
dependent Fit/gaps; it never rewrites incompatible historical records. A correction that
only changes Emphasis or fact selection updates the document's own selection in place
instead of creating a new analysis.

### Current product contract

> A single candidate can create a job application, analyze the job, resolve only the
> decisions that require human judgment, produce and edit a fact-linked CV, validate and
> explicitly approve its exact current content, render a valid and ATS-readable PDF,
> understand every blocker and available action, and track the recruitment process
> through the Web client backed by one application layer.

The Web UI must not require the user to know entity IDs, hashes, filesystem
paths, database details, or architecture. Those details remain available in provenance
views and diagnostic interfaces.

## 3. Product boundaries

- The domain must not hardcode `Matan`, a particular filename, or another candidate
  identity. A single `CandidateContext` supplies the candidate-specific policy.
- There is no candidate selector, candidate CRUD, or multi-candidate UI.
- Facts, Profiles, selection policies, prompts, task contracts, and rendering rules
  remain version-controlled files and independent sources of truth.
- The Web UI is the product interface and reaches the system only through the API.
  Worker and adapter boundaries are defined by the architecture specification.
- The application officially targets macOS. Portable code is preferred, but Windows and
  Linux do not block release.
- The UI supports current Chrome/Chromium. No other browser is claimed, because none is
  verified. PDF rendering always uses Playwright-managed Chromium.

## 4. Scope

The product includes:

- A Hebrew, desktop-first Web UI with basic responsive behavior.
- Job creation from required pasted text, an optional provenance URL, and a browser-read
  `.txt` convenience input.
- Immutable JobSnapshots, immutable versioned JobAnalyses, one mutable CVDocument per
  Application (selection and content), narrow immutable provider-response artifacts, and
  append-only immutable Submissions and audit history.
- Duplicate warnings based on identical URL, normalized-text hash, and a light
  company/title heuristic. A duplicate never refuses creation permanently: the first
  attempt is refused (412) until the caller resends with explicit acknowledgement, then
  creation proceeds.
- Deterministic action policy with analysis issues, Fit, and gaps presented as diagnostics.
- Track, Profile, Emphasis, language, requirement coverage, fact selection, and pending
  fact creation through the preparation flow.
- A structured section/bullet editor, fact inclusion/exclusion, deterministic changes,
  targeted AI regeneration, free-text edits, optimistic autosave, and isolated HTML
  preview.
- Full deterministic validation before approval and browser/PDF/ATS validation after
  rendering.
- Explicit Web approval that stamps the document's exact current content as approved.
- A Ready state derived, on every read, from the document's own approval and render
  stamps against its current basis (document content plus the facts it depends on).
- A dedicated candidate-facts surface for listing and inspecting candidate facts,
  creating pending facts, explicit confirmation and promotion, canonical correction
  through a replacement fact, and attachment to existing Profile sections. Contextual
  claim capture and use remain available in preparation flows. This surface is not a
  general Knowledge Manager and does not edit Profile definitions or arbitrary Knowledge.
- Structured AI Proposal tasks, including separate claim-support review when its
  evidence lifecycle in sections 10–12 is implemented.
- Deterministic work from an existing JobAnalysis through Ready without further AI;
  creating a new JobAnalysis requires a configured AI provider.
- A Dashboard, Application Detail, unified timeline, recruitment tracking, next action,
  internal and external submissions, status correction, and overdue warnings.
- Recruiter-facing PDF download and human-readable provenance/decision Markdown export.
- Explicit schema upgrade and reconciliation commands. PostgreSQL and remote-bucket
  backup/restore remain environment responsibilities rather than application commands.

## 5. Explicit non-goals

The following are not part of the product:

- Multiple candidates or candidate administration.
- Authentication, multi-user/tenant behavior, sync.
- Additional structured-state databases, ORMs, or broad storage-provider abstractions
  beyond PostgreSQL/SQLAlchemy Core and the local/S3-compatible object stores.
- Automatic job extraction from URLs, LinkedIn, or JS-heavy sites.
- Job-description PDF parsing or arbitrary file uploads.
- Additional AI providers or a provider selector.
- Cover letters, LinkedIn messages, recruiter emails, or other document types.
- AI-generated decision explanations.
- Autonomous AI extraction/linking of arbitrary edited claims. Review of wording
  against explicitly supplied canonical fact links is in scope under §10–12; review
  does not create canonical facts or grant access to facts outside the allowed pool.
- Arbitrary user prompts, arbitrary provider model IDs, or per-operation model selection.
- A general Knowledge Manager or arbitrary Web editing of Knowledge files, Profiles,
  policies, prompts, taxonomies, or rules. The dedicated candidate-facts lifecycle
  surface defined in scope is not a general Knowledge Manager.
- A general WYSIWYG editor, section reordering, or drag-and-drop.
- Mobile-first flows or a full internationalization framework.
- Notifications, calendar integration, recurring reminders, or follow-up automation.
- Charts, advanced analytics, or Web CSV export.
- General CSV or data import.
- WebSocket or SSE progress transport.
- Automatic application or schema updates.

No non-goal may enter the product as a supposedly small convenience without an explicit
scope decision.

## 6. Core invariants

1. `Application` is the container for one target job and its history.
2. The application represents one candidate. Candidate identity is not a dimension on
   every Application row.
3. `CVDocument` is the only mutable resume document and there is exactly one per
   Application once its first analysis has activated.
4. JobSnapshot, JobAnalysis, provider-response Artifact, Submission, and completed
   Operation records are immutable/versioned as specified. `CVDocument` is mutable.
5. Editing an approved or Ready document is allowed at any time. It changes the
   document's basis, so the document returns to `draft` on the next read; no command
   reopens it separately, and no new document or history record is created by editing.
6. `ready` is not a stored entity or a frozen artifact set. It is a state derived, on
   every read, from comparing the document's `rendered_basis`, `approved_basis`, and
   current `basis` (`state-and-use-cases.md` §3, §5). Precedence between derived states
   is defined exclusively there.
7. Approval requires a passing content check for the document's exact current content
   (`document_hash`) and the exact current state of every fact it depends on
   (`facts_hash`) — together, its `basis`. `approve_document` runs that check and
   approves in one action.
8. Any change to the document's content, selection, or analysis pin, or to a fact it
   depends on, changes the basis; a stored content report becomes outdated the moment
   `checked_basis` no longer equals the current basis.
9. Unsupported, pending, unlinked, strengthened, or semantically unverified claims may
    be saved in the editor but must block approval.
10. The presence of a valid fact ID does not prove that generated wording is supported;
    semantic factual validation remains mandatory.
11. AI outputs are Proposals. Schema validation, deterministic policy, factual
    validation, and application commit decide what becomes state.
12. AI failure never triggers a silent deterministic fallback. The user may explicitly
    retry or continue deterministically.
13. A provider output, cancelled output, or stale-operation output may exist as inactive
    immutable evidence, but it never becomes current without a successful optimistic
    commit against its original preconditions.
14. Recruitment lifecycle and preparation lifecycle are independent.
15. Recruitment history is append-only. Corrections add events and never rewrite past
    events.
16. A Submission's copied content and rendered files are never overwritten or
    automatically deleted. The mutable `CVDocument` they were copied from keeps
    changing after submission; the Submission does not.
17. No mutable content has two simultaneous sources of truth. Storage ownership is
    defined in the architecture specification.
18. `delete_fact` and `delete_application` are soft deletes: a terminal disposition flag
    on an otherwise-mutable row, appended to its audit trail like any other transition.
    Neither ever removes a row, rewrites prior content, or touches an immutable table.
    A deleted Fact or Application is excluded from default active listings but remains
    individually reachable, and every immutable record already produced from it
    (JobSnapshot, JobAnalysis, provider-response Artifact, Submission) and its own
    CVDocument are preserved unchanged.
19. Every Submission stores exact provenance sufficient to identify its candidate
    context, job context, knowledge context (the facts the submitted content depended
    on), policies, prompts, provider execution, and files. Because the document itself
    keeps changing, this provenance is what proves what was actually sent.
20. Normal queries never expose partially committed cross-store mutations.
21. API and worker concurrency must remain correct through optimistic versions, atomic
    PostgreSQL claims, leases, idempotency where required, and commit-time precondition
    checks.
22. A fresh installation starts with an empty database and is proven through its own
    workflow.

## 7. Candidate and application behavior

One CandidateContext is loaded from Knowledge. It points to canonical identity and
contact fact IDs and supplies display/filename policy, locale, and timezone. Candidate
names and contacts remain canonical facts rather than duplicated metadata.

The recruiter-facing filename uses the configured Latin candidate name by default,
including for Hebrew CVs. CandidateContext may override it. Renderers and filename
normalizers must not contain a candidate literal.

Knowledge, artifacts, temporary files, and logs use fixed directories below the project
root. There is no selectable root, marker, or runtime identity file.

## 8. Job intake and snapshots

The initial form requires company, target role, and full job text. Source URL is
optional. Mutable notes belong to Application Detail and do not burden the creation
form. An optional source label, when supplied by a snapshot-creation client, is
JobSnapshot provenance inside `source_metadata`; it is not a second mutable Application
field and the primary Web UI need not expose it.

The Web intake form autosaves an exact browser-local recovery copy that survives a page
reload or a later browser session. Duplicate choices, network failures, and validation
refusals do not discard entered values. Storage failures are visible and never block
editing or submission. Successful creation clears only the recovery copy for the intake
that was created; newer unsent edits remain recoverable. This copy is not a JobSnapshot
and grants no lifecycle or approval authority.

The `create_application` command is deterministic and fast. It creates the Application
and its first immutable JobSnapshot and does not call AI. In the Web intake flow, a
successful creation is immediately followed by a separate `analyze_job` Operation for
the returned snapshot. If queueing that Operation fails, the created Application remains
the destination and the explicit Analyze action remains available; creation is never
retried as part of that fallback.

The backend stores the exact text string it received without line-ending normalization.
It stores a source hash over that received representation and a separate normalized
hash for deduplication. A browser-read `.txt` file only populates the editable text
area; no file is uploaded. URL is provenance only, is never fetched, and uses soft
syntax validation plus explicit length/control-character limits.

Editing job text creates a new immutable JobSnapshot. The old snapshot and every
analysis produced from it remain historically valid for their own context; the document
itself does not change until the user explicitly runs `build_from_analysis` against a
newer analysis.

Duplicate detection runs before creation for UX and again inside the create command.
The user may open an existing Application or explicitly create another. A duplicate is
never a dead end, but the create command does refuse the first attempt: when matches
exist and the caller has not set `acknowledged_duplicates`, `create_application` raises
`DuplicateAcknowledgementRequired` (412) instead of creating the Application. Creation
proceeds once the caller resends the same request with `acknowledged_duplicates=true`.

## 9. Analysis, selection, and review

JobAnalysis owns classification, normalized requirements, analysis issues, and source
coverage. Fit and gaps are pure projections of its requirements. It is immutable; each
analysis is its own version. The document's `selection` field owns selected, excluded,
and pinned facts, content emphasis overrides, and candidate accounting; it is part of
the mutable CVDocument, not a separate versioned entity.

The first successful `analyze_job` commit for an Application creates the immutable
JobAnalysis and, in the same transaction, creates the CVDocument pinned to it with that
analysis's deterministic selection and no content. A later `analyze_job` on the same
Application creates a new immutable JobAnalysis but never touches the existing document;
it surfaces as the `DOCUMENT_ON_OLDER_ANALYSIS` warning until the user explicitly runs
`build_from_analysis`. An AI `propose_selection` task is an optional, separate Operation
that may propose a replacement selection while the document has no content yet; it is
never required to make the no-review path draftable. Its input includes each Profile
section's allowed fact IDs, claim budget, facts already occupying that budget, and
remaining pin capacity. The deterministic selection policy still validates every
proposed selection before activation.

A change to the meaning or classification of a requirement creates a new immutable
JobAnalysis; the document is not changed by that alone. A change only to which facts
address an already understood requirement, or to the Emphasis override, updates the
document's own `selection` in place.

Fit, analysis issues, and gaps are displayed but never require acknowledgement. Review is
reserved for active-context integrity problems such as an unresolved pending/deleted fact
on which the document's selection or claims depend. When those are absent and
the global auto-generation setting has been turned on -- it is off by default -- the
workflow may continue to drafting.

Analysis Review is a local form (`apply_analysis_decisions`). A classification change
creates one new immutable JobAnalysis rather than one version per toggle; an Emphasis or
fact-selection decision instead updates the document's selection in place, exactly as a
direct selection change does.

## 10. Drafting and editing

DraftDocument structured data is the source of truth. Mutable JSON and mutable Markdown
must not coexist as independent sources. Markdown and HTML are projections.

The editor primarily works with sections and bullets. Each claim exposes its text,
linked facts, claim status, warnings, and edit/regenerate/remove controls. Section order
is policy-controlled. The editor may offer simple up/down bullet controls if needed but
does not include drag-and-drop.

AI draft wording receives the facts permitted for each composed section. A selected fact
may support a claim only in a section that permits it; deterministic validation remains
authoritative over fact placement.

For reviewed wording, the read model exposes a safe explanation containing the review
policy version and assertion-to-source excerpts. Provider artifact identifiers and input
hashes remain internal. The editor labels this as semantic review rather than
deterministic proof, and warns that changing the exact wording invalidates that review.

A deterministic selection change (`update_selection`) updates the document's selection
synchronously, and updates its content in the same action only when the change requires
no AI and contains no semantic ambiguity. A change that needs wording judgment writes
nothing and instead directs the client to a regeneration Operation.

Free-text edits are preserved even when unsupported. They become pending or unlinked,
are immediately visible as unsafe, and block approval until supported through an
allowed deterministic proof or the reviewed-evidence path below, resolved through the
canonical fact lifecycle, or removed. Unlinked text requires explicit allowed fact
links before semantic review. A provider cannot autonomously turn edited text into
canonical facts or authorize its own wording.

A pending line linked to facts can be sent to semantic review exactly as written
(`regenerate_claim` with `keep_text`): no writer runs, and the line becomes reviewed
only on the §10.1 acceptance rule. A writer Operation reviews only the lines it wrote;
a pending line it left untouched is neither authorized nor failed by it.

The document headline is not a factual claim. Editing it keeps it the headline, and
deterministic validation accepts it only when it is one of the Profile's safe headlines.

### 10.1 Reviewed wording

Wording may paraphrase, shorten, or combine information from multiple canonical facts
without changing meaning. Each fact retains its identity; a combined sentence must
not invent a relationship, causal claim, employer, time period, or experience level.

Existing canonical/extractive/presentation proofs remain valid paths and need no AI
review. New wording requires hard checks and a separate semantic review against exact
sources and document context. The review must account for every factual assertion,
including protected values and attribution. Mere fact-ID presence, matching words,
an aggregate confidence score, or lack of a detected error is insufficient evidence.

Acceptance requires all hard checks to pass, complete positive review evidence, and
no known contradiction or unresolved uncertainty. Such wording needs no individual
user confirmation. Its provenance identifies semantic review rather than deterministic
proof. Known contradictions override positive review. Unsupported or strengthened
claims remain blockers; uncertainty requires focused clarification with the exact
sentence, context, and sources. General CV approval and accepted job gaps resolve neither.

A clarification that supplies new candidate information follows the fact lifecycle.
It cannot silently become wording evidence. Claim-specific human evidence must record
what was clarified against which sources and cannot override a known contradiction.
The precise clarification command and proposal-presentation lifecycle remain design
work; no generic acknowledgement endpoint is authorized as a bypass.

Review failure, cancellation, invalid output, missing assertion coverage, or stale
evidence cannot make wording eligible. Provider failure remains explicit, with no silent
fallback. Once a JobAnalysis exists, the deterministic downstream path continues through
Ready using its own proofs and without inventing provider-review metadata; creating a new
analysis still requires the configured provider.

Autosave uses debounce/blur and optimistic concurrency. A stale save returns a conflict
and does not overwrite. The UI shows the user's text and the current text for an
explicit choice; it performs no automatic merge.

Preview is server-rendered from the current DraftDocument through the same rendering
pipeline used for approved content where possible. It appears in an isolated iframe,
is clearly marked as draft, and does not generate a PDF on every edit.

A PDF of the document's current unapproved content is available on demand, before any
approval, at the Application's document resource. It is rendered synchronously through
the same composition and browser as `render_document`, stamped as an unapproved draft on
every page, and stored nowhere: it writes no document field, creates no Artifact or
Submission, and is not a `render_document` Operation. Seeing the layout therefore never
requires approving - approval stays the one explicit act that stamps `approved_basis`.

The HTML preview and this draft PDF are the document's `preview` and `preview.pdf`
queries (state-and-use-cases.md §20).

## 11. Validation, approval, rendering, and Ready

Editing runs lightweight claim, structure, and required-field checks. A full
deterministic content check (`check_document`) is explicit before approval, and
`approve_document` runs that same check as part of approving. Browser/PDF/ATS checks
run only after `render_document` activates.

A failed content check is a successful domain result with `passed=false` and structured
issues. An exception is reserved for a validator that could not run.

Pre-approval validation deterministically checks eligibility and currency of
the exact proof/review evidence for every claim. It does not call AI. Evidence binds
wording, language, supporting sources and their content, contextual attribution,
allowed-fact scope, and review-policy versions. Any change to the document's content,
selection, or analysis pin, or to a fact it depends on, changes the basis, so a stored
content report is shown as outdated the moment `checked_basis` no longer matches; the
next `check_document` or `approve_document` produces a fresh one. There is no
`ValidationRun` history: only the current report, stamped with the basis it was produced
for, is kept.

Warnings are visible and non-blocking. Approval may require one general confirmation
that warnings remain. Any item requiring a specific business decision is a blocker or
review reason rather than a warning.

Web approval is always an explicit trust-boundary action. `approve_document` stamps
`approved_basis` (and `approved_at`) on the document itself when the check passes and no
review reason or blocker exists; it does not create a separate frozen entity and does not
touch `content`. The document remains the one mutable resume document before and after
approval. Rendering is a separate use-case and may be chained by the UI. A render
failure does not revoke approval; the document stays `approved` and the user may retry
`render_document`. Editing an approved or Ready document is always allowed; it changes
the basis and returns the document to `draft` on the next read, which is the only way
approval is lost.

A no-pause flow that chains the check, approval, and rendering is an explicit user
approval instruction and is recorded as one, with `actor_type=user` and
the originating client. It never bypasses blockers or validation and never auto-approves
merely because an AI Operation completed. No interface offers this flow; the
guarantee binds whichever one does.

There is no prior Ready state to keep usable alongside a newer draft, because there is
only ever one document. A newer JobAnalysis than the one the document is pinned to does
not change the document or its `ready` state; it surfaces as the `DOCUMENT_ON_OLDER_ANALYSIS`
warning until the user explicitly runs `build_from_analysis`, which does replace the
selection and clears content and every stamp. There is no `newer_draft_in_progress` flag
and no revision comparison: the document either is `ready` for its current basis or it
is not.

The Ready screen contains preview, recruiter-facing PDF download, the current content
report, and the document's own provenance (its analysis, selection, and the facts it
depends on). It offers editing, which returns the document to `draft`, rather than
creating a new WorkingDraft.

## 12. AI behavior

The application implements one OpenAI adapter behind the provider-neutral `AIProvider`
protocol.
The AI task catalog has six implemented tasks. Task names
are the provider's; `analyze_job` is the application command that calls the first:

- `propose_analysis` — the posting's requirements with their importance,
  evidence-linked coverage, and the severity and reason of any shortfall,
  together with Track/Profile/Emphasis/language classification, as one Proposal
  from one call.
- `propose_selection`
- `draft_resume`
- `regenerate_section`
- `regenerate_claim`

The analysis task may not decide Fit, review routing, approval, or activation; those
stay with deterministic policy under §2.

A flawed part of a reading narrows that part and is disclosed as an analysis issue
rather than voiding the reading. A requirement whose text the engine cannot locate in
the posting is kept and marked unverified; an unresolvable citation is dropped and any
positive coverage resting on it falls to unknown. Uncertainty is recorded as unknown and
never as an absence of experience.

Coverage and shortfall severity answer different questions. `partial` says that
canonical facts answer only part of a requirement; it does not by itself say that the
uncovered part is material. A partial mandatory requirement is a hard gap only when its
shortfall severity is `material`. A `minor` or `unknown` shortfall remains a warning.
An `unsupported` mandatory requirement remains a hard gap. The provider proposes
shortfall severity and an explicit reason; deterministic policy normalizes inconsistent
combinations and remains authoritative over numeric and canonical boundary checks.
Qualitative wording such as strong, deep, excellent, high-quality, maintainable, or
large-scale is assessed semantically from the breadth, complexity, responsibility,
context, and demonstrated outcomes of canonical facts. A fact need not repeat the
modifier, provide a self-assessment, or attach a numeric proficiency level. Their absence
alone is not a shortfall. `partial` requires an identifiable substantive condition that
the evidence does not establish; when the facts do not permit a semantic determination,
the result is `unknown` rather than an invented gap.

- `assess_claim_support` — separate semantic review of wording against supplied
  canonical sources and contextual attribution, returning evidence proposals only.

In the first implemented lifecycle, generation and regeneration run writer then reviewer
inside one persisted Operation. Only complete `supported` evidence may activate wording.
`uncertain` and `unsupported` are terminal domain outcomes for that Operation: both
provider responses remain immutable inactive evidence, the document's `content` is not
changed, and retry/correction is offered. There is no acknowledgement bypass. A future
claim-clarification UI may add a richer inactive-proposal lifecycle without weakening
this acceptance rule.

The support reviewer runs separately from the writer and does not use the writer's
self-assessment as evidence. Separation of calls is not a guarantee of independent
judgment. Structured results distinguish support found, uncertainty, and unsupported
assertions; execution failure is separate. Application policy, not the provider,
decides whether the evidence satisfies §10.1.

Each task has explicit input/output schemas, semantic contract version, prompt version
and hash, and structured output validation. Calls are stateless and do not depend on a
prior response or hidden conversation.

The provider receives only the relevant JobSnapshot, canonical candidate facts required
for evidence matching, the profile catalogue, and the policies needed for the task. It
does not receive historical artifacts by default. The UI explains that job descriptions
and canonical candidate facts may be sent when AI is enabled; no per-call consent dialog
is required.

An OpenAI key is backend/environment configuration only. It is resolved through the
runtime configuration contract but is environment-only: `.env` and project config
cannot enable it. It is never stored in PostgreSQL, sent to React, or written to logs.
Settings expose only whether it is configured.

When a key is configured, `ai_enabled` defaults to true. New analysis uses that configured
provider; deterministic downstream commands remain explicit where applicable. There is
no ambiguous `auto` execution mode and
no dynamic model discovery. Settings offer a backend-supplied allowlist of supported
models and `low`/`medium`/`high` reasoning effort. The selected defaults are copied into
each new Operation, so a later settings change cannot alter queued work. Clients cannot
submit arbitrary model IDs or override one individual Operation.

Parsed output and a sanitized raw response are preserved. Raw responses are immutable
artifacts rather than PostgreSQL blobs. Response ID, model, usage, latency, hash,
refusal/error metadata, contract/prompt versions, the dated USD price snapshot, and the
derived execution cost are recorded. Cached input is accounted separately. Secrets and
hidden chain-of-thought are never retained.

Job descriptions and user content are untrusted data. They may influence the proposed
content but never policy, allowed facts, validation, approval, or output schemas.

Posting content can legitimately change extracted requirements and their
derived gaps. Prompt-injection instructions are not additional job requirements.
Acceptance compares the same posting with and without adversarial instructions:
actual requirements retain their interpretation, and injected instructions must not
add actionable requirements or alter derived coverage, gaps, Fit, or review decisions.
An exact quotation proves source presence, not legitimate requirement meaning.
Mock tests prove enforcement of specified contracts; live evaluation is required for
model behavior and is not a guarantee of universal injection resistance.

## 13. Preparation and recruitment

Preparation and recruitment are separate views.

Preparation state describes progress toward a usable CV. DocumentState restates the
document's own approval/render stamps (`draft`/`approved`/`ready`) against its current
basis. Recruitment status describes the application after it is saved or submitted.
Their exact values and transitions belong to `state-and-use-cases.md`. Recruitment never
changes preparation history, and `closed` is archival rather than a hiring outcome.

Every Application projection includes current preparation and document states, the
content check state, active context IDs, the document's own ID/hash/analysis pin,
review reasons and warnings, active Operation, available actions, blocked actions with
reason codes, and a nullable recommended action. These values are computed from one
consistent database snapshot. Payload integrity is verified after the database read
scope closes; the final policy is derived from the captured metadata and that
verification without holding a transaction across storage I/O.

The backend owns action policy. React does not implement a second state machine.

## 14. Recruitment tracking

The product includes a table Dashboard with search, filters, sorting,
preparation/recruitment state, last activity,
next action/date, active Operation, and warnings. It does not include charts.

Application Detail contains header/status/next action, current preparation, one unified
timeline, a focused document/provenance section and a submissions section, and
navigation back to the editor.

`submit_application` requires the document's `document_state = ready` (`rendered_basis
== approved_basis == basis`) and no review reason, copies its exact content and rendered
HTML/PDF to submission-owned paths with a SHA-256 per file, creates an immutable
Submission, transitions to `applied` if necessary, and appends status/audit history in
one PostgreSQL transaction. It never resolves `latest` inside the command; it records a
send that already happened and is not itself a validation gate. The document's analysis
need not match the currently active JobSnapshot/JobAnalysis; that case returns
`DOCUMENT_ON_OLDER_ANALYSIS` as a non-blocking warning rather than a precondition
failure. Multiple submissions are append-only and do not reset recruitment state, and
none of them changes the document.

`record_external_submission` is a distinct use-case. It records an immutable external
submission that carries no document content or files.

Backward transitions are not ordinary business transitions. A status error is fixed by
an explicit correction event with the corrected event ID and mandatory reason. The
current status is stored as a transactionally consistent projection; events provide
audit history rather than event-sourced reconstruction.

One next action and date may be active for an Application. Changes append events.
Overdue is a computed warning when the date is before today and the Application is not
terminal. There are no notifications.

There is no hard delete through Web. Applications created by mistake may move from
`saved` to `closed`, or be soft-deleted via `delete_application` (invariant 18, §6).
`delete_application` is orthogonal to `RecruitmentStatus`: it does not replace `closed`
and is available regardless of the Application's current status.

Audit actor identity is intentionally local and non-authenticated:

```text
actor_type: user | system
client:     web | worker
```

The primary UI may display `You` for `actor_type=user`; technical client identity
belongs to provenance rather than the normal timeline label.

## 15. Runtime and local security

The product is local-only, binds to loopback, and exposes the Web UI and API on the same origin in production.
It has no authentication and must not accept mutating request from arbitrary origins.
The API and Operation worker are separate processes over the same PostgreSQL database; neither supervises the other.

Safe UI settings are limited to automatic generation when review is not required,
`ai_enabled`, default execution mode (`ai` or `deterministic`), an allowlisted default
AI model and reasoning effort, and basic UI preferences: density, text size, and
shared theme (`system`, `light`, `dark`; default `system`). The server is authoritative
for theme. A local cache is only for startup display; an old local preference can be
imported only by explicit user selection under the current Settings ETag. Per-task overrides, timezone,
arbitrary model IDs, and secrets remain unavailable to the client.

## 16. Storage, provenance, and retention

Storage ownership and technical layout are defined by the architecture specification.

Storage keys and local paths are never API inputs. Downloads are addressed by artifact
ID, verify the registered content hash, and use a friendly filename.

Each Submission records a global knowledge-store version for coarse audit and the
document's exact `facts_hash` at submission time — the canonical content of every fact
its selection or claims depended on. An unrelated fact change does not automatically
affect the document's basis, because `facts_hash` only covers the facts the document
actually depends on.

The document's own `built_with` (profile version, selection-policy version) determines
the `PROFILE_CHANGED`/`POLICY_CHANGED` warnings by comparison against current versions;
approval and rendering always validate against the current values rather than trusting
`built_with`. There is no separate versioned SelectionPlan entity: the selection is part
of the document and part of its `document_hash`.

Approved, submitted, historical, and inactive Operation outputs are not automatically
deleted by registration or approval activity. Read-only orphan inspection reports
candidates whose destination holds no live write lease and no database reference; a
candidate still covered by an unexpired lease is never listed in the first place.
`reclaim_orphans` (state-and-use-cases.md §19b) removes a candidate only after fencing
its write lease and then explicitly checking, before deleting anything, that nothing
registered references it - fencing rules out a future registration, but the deletion
decision itself comes from that check, not from fencing alone. A candidate with no
lease at all, including one an old writer's late storage write produced after an
earlier reclaim already removed its lease and files, is checked and removed the same
way. Reclaim guarantees no registered payload is ever removed and no reclaimed write
ever completes registration; it does not guarantee a single call removes every orphan,
since the underlying object-store write is not itself fenced and may still land after
its lease is gone, leaving that case for a later call to remove (architecture.md §7.1).

There is no archived copy of replaced content. `build_from_analysis` and ordinary
editing overwrite `content`; only a Submission keeps what was sent (decision record §3
item 10).

## 17. Knowledge lifecycle

Knowledge stays file-based and version-controlled. UI writes follow:

```text
React -> FastAPI -> FactLifecycleService -> validate/stage -> PREPARED journal
      -> activate files -> atomic fact events/plan + COMMITTED journal
```

File staging, activation, restoration, and cleanup run outside database scopes. The
application owns the short database scopes through KnowledgeLifecycleStore; audit and
the journal do not replace canonical file-backed Knowledge.

The application never performs an automatic Git commit.

New facts receive UUIDv4 technical IDs. Existing semantic fact IDs remain valid, but
nothing creates new ones.
The UI does not expose fact-ID creation. A system-generated human slug may exist but is
not identity.

The Web supports these lifecycle operations both on the dedicated candidate-facts
surface and, where the operation depends on a claim or active analysis, in its contextual
preparation flow: viewing facts, creating a pending fact, explicit confirmation/promotion,
attachment to an existing Profile section, and selection in the Application's document.
The dedicated surface may list valid attachment targets; listing them does not grant
Profile editing. The shortcut `Confirm and add to source of truth` still records
pending -> confirmed -> canonical transitions separately. `Confirm and use` is one
logical command that promotes, attaches, and updates the named Application's document
selection (`update_selection`), or reports a complete failure.

Creating a fact from a claim copies the exact user text without AI rewriting. Meaning,
tags, provenance, dates, and other metadata require explicit input.

Canonical corrections create a new fact with a `replaces` relationship rather than
mutating old content. `POST /api/v1/facts` accepts `replaces`; the new fact enters at
`pending` like any other, so a correction is confirmed and promoted explicitly.

This candidate-facts surface does not add deletion, archival, withdrawal, retirement,
or a `known-incorrect` transition. Those operations have distinct consequences for
Profile pools, selection, stale drafts, warnings, and historical evidence and require a
separate approved lifecycle contract. Canonical facts are never edited in place.

Cross-store Knowledge mutations use a narrow durable journal with old/new hashes,
paths, staged path, DB mutation identity, and deterministic recovery. An unreconciled
mutation quarantines additional promotion and approvals that depend on Knowledge, but
does not block read-only history, export, or recruitment tracking.

Superseded facts add historical warnings. A fact known to be incorrect receives a
stronger historical warning. Neither case rewrites an already-copied Submission.

Manual edits to the Knowledge files remain supported. Before a relevant command, the
backend re-reads or re-hashes exact dependencies instead of trusting a long-lived
cache. A change produces `knowledge_changed`/`SOURCE_CHANGED`; it is never silently
reloaded into an editor form currently open by the user.

## 18. Operations and failure behavior

Long-running AI analysis, generation/regeneration, rendering, and materially long
browser validation run as persisted Operations outside HTTP requests. Ordinary saves,
approval, selection editing, and recruitment status changes remain synchronous.

Operation status and failure reason are separate. Lifecycle values and command behavior
are defined in `state-and-use-cases.md`.

Queued cancellation is immediate. Running cancellation is best-effort and prevents
activation. A completed output after cancellation is recorded as inactive evidence.
Retry creates a new Operation with `retry_of_operation_id` and a new idempotency key.

Concurrency, lease, idempotency, and automatic-retry mechanics are defined by the
architecture specification; their observable command outcomes are defined by
`state-and-use-cases.md`.

## 19. API and UX contracts

The HTTP API is `/api/v1`. It exposes application use-cases without leaking database or
filesystem representations. Asynchronous work returns an Operation reference.

The document is read and written at the Application's document resource, with
`document_hash` carried as its ETag. The autosave `update_document` uses If-Match and
returns `409 Conflict` on mismatch; every other document command carries
`expected_document_hash` in its body and returns the same `409` on mismatch, because an
action on a resource is not a conditional replacement of it. Domain precondition
failures such as a blocked approval return `412`. Problems use a stable Problem Details
body with machine code and safe context. Technical details stay in logs.

A review reason and a failed content check (`passed=false`) are successful domain
outcomes, not HTTP errors. The API enforces an explicit body-size limit; oversized job
text returns `413 Payload Too Large`.

Data export uses a versioned v2 schema. A compatibility format is added only when a
real existing consumer is identified; v2 does not create speculative compatibility.

## 20. v2.0 Definition of Done

v2.0 is Release Ready when a user can complete the Web workflow from job intake through
a validated Ready PDF, understand and resolve every blocker, and track the subsequent
recruitment lifecycle without knowing technical identifiers or architecture. The
workflow must preserve every invariant in this specification, including immutable
history, exact approval provenance, unsupported-claim blocking, concurrency safety,
recoverable Operations, and deterministic work from an existing analysis through Ready.

The executable evidence and release matrix are defined exclusively in
`test-and-acceptance-plan.md`.

## 21. Change and stop conditions

Implementation proceeds without approval pauses for naming, folder structure, or other
internal details that preserve contracts. Work stops for an unresolved semantic
conflict, scope expansion, migration/data-loss risk, a path that could allow unsupported
claims through approval, a required deployment-model change, or any proposed dual-write
behavior.
