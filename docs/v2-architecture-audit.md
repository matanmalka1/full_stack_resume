# v2 Architecture Audit — responsibility boundaries in `cv_engine`

Status: **Stages 1–6 implemented and verified; stages 7–8 not started (2026-08-18)**

Scope: `cv_engine` module and file responsibility boundaries at M1 close, before M2
begins. Baseline commit: `a68bcec`.

Authority: `docs/v2-architecture.md` (binding boundaries), `docs/v2-product-spec.md`,
`docs/v2-state-and-use-cases.md`, `docs/v1-upgrade-handoff.md`, `CLAUDE.md`.

This document records what was found, what the target organization is, what will be
moved in which order, and — deliberately — what will **not** be split. It changes no
behaviour and authorizes no refactor by itself.

## 0. Constraints this audit works inside

- `docs/v2-architecture.md` §3 fixes the top level as `domain/ application/
  infrastructure/ api/ cli/ runtime/` plus `frontend/`, and states: *"Subpackages are
  introduced only when the amount and cohesion of code justify them. There is no
  one-file-per-interface rule and no micro-packaging objective."*
- §3.2 names the application seams: `ApplicationService`, `AnalysisService`,
  `DraftService`, `RenderingService`, `TrackingService`. A `use_cases/analyze_job.py`
  layout would replace an approved contract and is therefore out of scope. The code's
  seven service classes already map to the command families in
  `docs/v2-state-and-use-cases.md` §12–§20.
- §3.1 assigns the domain *"lifecycle rules, validation semantics, transition rules, …
  Ready qualification"*.
- §3.3 names the M2 repository split, which is what will eventually justify an
  `infrastructure/persistence/` package.
- `CLAUDE.md`: validation behaviour, fact semantics, statuses, and artifact lifecycle
  may not change silently; hard failures must keep blocking `ready_qualified`.

**Verified before anything else: the import graph has no layering violations.** Every
`domain/*` module imports only siblings, `..util`, stdlib, and pydantic; every
`application/*` module imports only `..domain.*`, siblings, and `..util`; infrastructure
imports inward. The findings below are not import-direction problems. They are product
policy sitting in the wrong layer, and one invariant with three independent authors.

Three of the four hypotheses that prompted this audit were **not** confirmed as stated:

| Hypothesis | Finding |
| --- | --- |
| `services.py` is too big and too generic | The *file* is 1130 lines, but it holds seven cohesive service classes that match the approved §3.2 seams. The problem is file-level packaging, not design. |
| `analysis.py` concentrates too many policies | Confirmed — eleven distinct policies with different change triggers behind a three-symbol public surface. |
| `util.py` is becoming a utility graveyard | Not yet: 53 lines, but two of eight functions are already **dead** and two more have a single consumer. |
| `infrastructure/` is getting too flat | Not yet: eight modules with distinct names. The boundary that would justify subpackages is M2's repository split. |

---

## 1. Findings by severity

### Critical

**A1 — `ValidationReport` is constructed in three places with three different pass
formulas, and the `"filename"` group means two different things.**

- `cv_engine/domain/validation.py:319-324` — `passed=all(groups.values()) and not
  any(issue.hard …)`; groups `{content, profile, structure, filename}`; here `filename`
  means headline safety (`code="unsafe-headline"`, `:315-317`).
- `cv_engine/infrastructure/rendering.py:189-198, 260-271` —
  `passed=all(groups.values())`, **without the `hard` term**; groups `{render,
  page_count, pdf, ats, links, visual, direction, filename}`; here `filename` means the
  PDF file name (`code="filename"`, `:255-258`).
- `cv_engine/application/ready.py:29-56` — a third hand-rolled construction with its own
  group set and a local `fail()` closure.

`ValidationReport.passed` is the single gate on approval, `PreparationState=ready`, and
submission (`docs/v1-upgrade-handoff.md` §14). Three authors means the soft/hard
distinction can diverge per site. Today `validate_rendered` pairs every issue with
`groups[x] = False`, so the missing `hard` term is latent rather than live — but nothing
detects the next issue added without that pairing.

**A2 — the READY-demotion rule lives in two layers, and the repository orchestrates it
outside its own transaction.**

- `cv_engine/infrastructure/db.py:466-478` (`save_analysis`) re-reads status *after its
  transaction has closed* and calls `self.transition_status(… PREPARING, "new analysis
  invalidated the prior ready version")`. Two transactions, not atomic.
- `cv_engine/application/services.py:946-951` (`approve`) expresses the same invariant
  with a different trigger and reason string.
- "READY is not settable through the generic transition" is stated three times:
  `db.py:506-511` (raise), `cli.py:175` (parser `choices` filter), `services.py:1053`
  (`set_ready` only after a fresh verify).

**A3 — default-emphasis policy is resolved two different ways inside one file.**
`cv_engine/domain/analysis.py:251-262` hardcodes a per-profile map, while
`analysis.py:142,150` in the same file reads `profiles.get(profile).default_emphasis` and
`.allowed_emphases` from the Profile store. The YAMLs are the declared source of truth
(`docs/v1-upgrade-handoff.md` §4 principle 2: *"Facts → Profiles → Rendering Rules are
separate layers"*).

**Verified: the hardcoded map currently agrees with all ten `profiles/**.yaml`
`default_emphasis` values, so there is no live divergence.** Nothing would detect the
next YAML edit. `classify_job` takes no `ProfileStore`, which is why the map exists.

### High

**A4 — Ready validation groups 4–10 are implemented in the rendering adapter.**
`cv_engine/infrastructure/rendering.py:180-288` owns the page-count rule (`maximum = 2 if
profile.allow_two_pages else 1`), the ATS threshold (`coverage < 0.9`), a second and
different `0.9` token threshold in `_claim_recoverable:274-288`, expected-link
derivation, the overflow tolerance (`+ 1` px, inside JavaScript injected at `:163-173`),
RTL isolation, and the filename rule. Add `normalized_role_filename:31-37` — which
carries a hardcoded `"B2B Sales"` fallback role — and `MIXED_LTR:24-28`.
`docs/v2-architecture.md` §3.1 assigns Ready qualification to the domain, and
`tests/test_candidate.py:32` already lists `"infrastructure/rendering.py"` in its
`POLICY_MODULES`: the test suite classifies this file as policy.

**A5 — `DraftService.approve` (`application/services.py:849-958`) is 110 lines holding
five concerns.** Version numbering (`version = len(existing) + 1`, `:859-863`); two
14-argument `register_artifact_version` calls differing only in type, logical name, and
path (`:873-886`, `:887-900`); the renderer invoked to *predict* output filenames so the
record can name paths that do not exist yet (`:903-908`); a 22-key decision-record
payload assembled inline (`:910-936`), in which `accepted_warnings_or_gaps` and
`user_overrides` carry the same value; a prose summary string (`:943`); a status
transition (`:946-951`). The decision record is the reproducibility contract
(`docs/v1-upgrade-handoff.md` §16 and §4 principle 13) and has no typed shape anywhere.

**A6 — product policy in `cli.py`, invisible to the architecture test.**

- `cli.py:356-363` maps `confirm`→`CONFIRMED` and `promote`→`CANONICAL` and refuses
  without `--confirm`, while `KnowledgeService.promote_fact:308-331` accepts
  `explicitly_confirmed` as a parameter and **never checks it** (the CLI passes `True`
  unconditionally at `:367`).
- `cli.py:569-571` routes `status applied` to `tracking.submit` rather than a transition.
- `cli.py:627-630` defines the composite reconcile AND-rule.
- `generic_reconcile:375-385` re-implements the artifact-integrity rule.
- `export_csv:256-294` owns `EXPORT_SCHEMA_VERSION`, a frozen 19-column contract, an
  `isinstance` fork between `ApplicationListView` and the infrastructure `Repository`,
  and writes an undocumented second `.meta.json` file.

`tests/test_architecture.py:116` iterates only `("domain", "application")`, so `cli.py`,
`compat.py`, `runtime/*`, and all of `infrastructure/` are unconstrained by it.

**A7 — the same artifact-integrity rule exists four times.** `cli.py:375-386`;
`infrastructure/migration.py:809-822` (identical message strings, raw SQL instead of
`artifact_inventory()`); `application/ready.py:67-74,145-166` (different issue codes);
`migration.py:757-763` (different messages again).

**A8 — `compat.Engine` owns behaviour and is the de-facto tested surface.**
`Engine.fast` (`compat.py:217-252`) is a real six-step use case with its own gates that
exists nowhere in the application layer. `compat.py:99-111` *un*-translates errors,
digging `__cause__` back out to re-raise the domain `FactStoreError` the service just
wrapped. `compat.py:64-65` reads `services.knowledge.base_dir`, which is not a member of
the `KnowledgeStore` Protocol (`application/ports.py:80-100`). `tests/conftest.py:229-345`
builds every workflow fixture (`analyzed_ → drafted_ → approved_ → ready_application`)
through it — so the layer `docs/v2-architecture.md` §3.4 says to remove is what the suite
actually exercises.

**A9 — a production rule is verified against its own copy.**
`tests/helpers.py:92-96 seal_report` is a verbatim re-implementation of
`infrastructure/migration.py:55-58 _seal_report`. A change to the migration sealing rule
would pass the tests.

**A10 — `ServiceBase` inherits on the wrong axis.** Of eleven helpers, **seven are pure
port-error translation** (`try: port.call() except OSError: raise
InfrastructureFailure`), and **six are used by exactly one subclass** (`candidate`,
`fact_store`, `store_working_draft`, `working_markdown`, `stored_draft`,
`artifact_text`). Only `_bound_analysis:175-201` and the `renderer` guard carry a rule.
`candidate(facts=None)` ignores its argument entirely (`:132-133`).

### Medium

| # | Location | Finding |
| --- | --- | --- |
| A11 | `application/services.py` | 1130 lines, seven service classes in one file. File-level packaging, not design: the seams match §3.2. |
| A12 | `domain/analysis.py` | Eleven distinct policies — language detection `:69-73`, term tables `:36-66`, profile scoring `:211-221`, track resolution `:223-243`, confidence `:245-249`, emphasis default `:251-263`, gap rules `:265-325`, fit derivation `:96-99`, approval routing `:16,20-34,76-93`, proposal merge `:102-200`, keyword extraction `:336-343` — behind a **three-symbol public surface** (`classify_job`, `merge_classification`, `unresolved_approval_reasons`). Every other symbol has zero external importers. |
| A13 | `domain/validation.py` | `validate_draft` is one 280-line function (`:45-324`) holding roughly twelve policies over four groups, including a candidate-specific prohibited-wording table (`STALE_OR_UNSUPPORTED:14-18`) beside structural and approval-routing rules. |
| A14 | `domain/drafts.py` | Two change axes: document assembly and claim edits (`build_draft`, `apply_claim_edit`, `render_composite_claim`, `validate_derived_wording`) versus the Markdown projection and round-trip codec (`_marker`, `_render_claim`, `serialize_markdown`, `_decode_claim_line`, `_extract_marked_claims`, `synchronize_markdown_claims`, roughly 200 lines). |
| A15 | `services.py:756-779` | `validate_working` is read-named but writes (`store_working_draft` at `:768`) and swallows a failure (`except ValueError: pass`, `:763-766`). |
| A16 | `application/ports.py` | Port over-breadth: `TrackingRepository:265` declares no members of its own; `ApplicationService` receives a ten-method `ApplicationStore` and uses one; `QueryRepository` offers roughly 29 methods for six used. `register_artifact_version:212` is declared `(*args: Any, **kwargs: Any)`, so the payloads in A5 and A7 are not contract-checked. |
| A17 | `services.py` | Duplicated orchestration: the knowledge-unpack prologue **five times** (`:671,757,791,826,965`); the `validate_draft → record_validation` tail **five times**, differing only in a phase literal (`:723,769,810,837,990`); `edit_claim` and `sync_working_claims` share an identical twelve-line body; `ApplicationMutationResult` is built three times in `TrackingService`. |
| A18 | four files | Version literals scattered: `"rules-v1"`, `"system-v1"`, `"1.0.0"` (`services.py:589,737-745`); `ai/prompts/system-v1.md` (`runtime/composition.py:70-72`); model default `"gpt-5.6"` (`runtime/config.py:36`) and `"gpt-5.6"` (`cli.py:145`) versus `"rules-v1"` (`application/commands.py:37`) — three different defaults for one setting. §17 requires explicit version surfaces. |
| A19 | `domain/analysis.py:272-317` | Gap rules hardcode nine canonical fact IDs. All nine exist today; nothing validates that they still do, so gap policy silently changes whenever the fact store is renumbered. |
| A20 | `util.py` | `slug:35` and `safe_relative_path:40` have **zero callers**. `sha256_bytes` is used by one module (`infrastructure/legacy_source.py`); `normalized_text` by one (`infrastructure/rendering.py:222,276`). `utc_now`, `sha256_text`, `sha256_file`, and `canonical_json` genuinely span every layer. |
| A21 | `domain/models.py:513-524` | `ProviderContext` and `ProviderTaskResult` are provider transport DTOs whose only importer is `infrastructure/providers.py`. |
| A22 | `runtime/` | Knowledge and storage layout decided in the runtime layer: `KNOWLEDGE_DIRS` (`workspace.py:15`), `"applications.sqlite3"` (`:99-100`), the prompt path (`composition.py:70-72`). `installation_id():115-132` **writes a file** from read-only-looking CLI paths (`cli.py:415,421`). `composition.py:73-92` splats one `shared` dict into all seven services, so `ApplicationService` holds a renderer and a provider it never uses. |
| A23 | package-wide | `sha256_text(canonical_json(...))` appears twelve times; only `migration._content_hash:35-40` factors out the "pop the hash field" variant. Three `json.dumps` conventions coexist. Four path-containment implementations with **different symlink semantics**: `util.py:40-50` (dead, part inspection), `legacy_source.py:76-83` (part inspection), `workspace.py:102-113` and `migration.py:244-253` (resolve plus `parents`). |
| A24 | `migration.py:294-310` | Library code spawns the test suite via `subprocess.run([… "-m","pytest","tests/test_migration.py"])`, and `migration_gate:529-531` calls it by default. Production code depends on `tests/`. |
| A25 | `tests/` | No coverage at all for `list_facts`, `show_fact`, `knowledge_versions`, `reconcile_facts`, `link_claim`, `sync_working_claims`, `list_applications`, `latest_decision`, or most CLI branches (`reconcile`, `export`, `status`, `validate`, `approve`, `render`, `ready`). `TrackingService.transition_status` and `set_next_action` are exercised only through `Repository` (`tests/test_database.py`), never through the service. |

### Low

- **Naming**: `services.py` (a module of seven services), `db.py` (schema, repository,
  and lifecycle policy in one), `util.py`, `ServiceBase`. Three classes cover one
  aggregate: `ApplicationService` (create), `ApplicationQueryService` (read),
  `TrackingService` (mutate status). `chain.py`, `ready.py`, `ports.py`, `errors.py`,
  `commands.py`, `queries.py`, `presentations.py`, and `selection.py` are good names and
  should stay.
- `services.py:822-823 link_claim` is a one-line alias inside the service; `cli.py:13`
  imports `connect` unused; `migration.py:20` imports `sha256_bytes` unused;
  `ContactScheme` and `OverrideKey` have no external importers; `runtime/workspace.py:9`
  reaches into `domain/models` only for `StrictModel`.
- `infrastructure/knowledge.py:48-85` repeats the same JSON-load-with-typed-error block
  four times, differing only in the exception class. `FACT_SOURCE_NAMES` exists twice
  (`domain/facts.py:11`, `migration.py:625`), plus three inline literals in
  `migration.py:328,439,575` and again as `CANONICAL_SOURCES` keys in
  `canonical_data.py:155-160`.
- `domain/facts.py:68` builds `f"base/{name}"` — storage layout inside the domain, which
  the architecture test's AST path check misses because it only matches the `/` operator.

---

## 2. Responsibility map

```text
application/services.py  (1130)
  current: 7 service classes + a shared base
  keep together: each class's own methods (they match §3.2 seams and §12-§20 commands)
  move: the file becomes a package, one module per service          -> application/services/
        approve's decision-record payload construction              -> a typed domain record (stage 7)
        version numbering / lifecycle-status literals               -> domain (stage 7)
        7 error-translation helpers off ServiceBase                 -> port adapters (stage 7)

domain/analysis.py  (363)
  current: vocabulary, scoring, track, confidence, emphasis default, gap rules,
           fit, approval routing, AI-proposal merge
  keep together: term tables + scoring + track + confidence (one read of a posting)
  move: gap rules + fit                                             -> domain/analysis/gaps.py
        thresholds + override routing + proposal merge               -> domain/analysis/approval.py
        hardcoded default-emphasis map                              -> Profile store (stage 8)

domain/drafts.py  (604)
  current: document assembly, claim edits, Markdown projection, Markdown round-trip
  keep together: build_draft + apply_claim_edit + composite/derived wording rules
  move: serialize/parse/marker codec + synchronize_markdown_claims  -> domain/draft_markdown.py

infrastructure/rendering.py  (327)
  current: Jinja render, Chromium/PDF, and Ready groups 4-10
  keep together: template render + Chromium drive + pypdf extraction
  move: validate_rendered, _claim_recoverable, thresholds,
        normalized_role_filename, MIXED_LTR                         -> domain/render_validation.py (stage 8)

infrastructure/db.py  (956)
  current: schema DDL, connect/initialize, UnitOfWork, repository SQL,
           and the recruitment lifecycle rules
  keep together: DDL + connection + UnitOfWork + SQL accessors
  move: ALLOWED_TRANSITIONS + transition validation                 -> domain/recruitment.py (stage 6)
        _set_ready / _record_submission / record_decision rules      -> domain/application (M2, §3.3)
        save_analysis's post-commit status orchestration             -> application layer (M2)

cli.py  (650)
  current: parsing, formatting, export contract, reconcile, and product policy
  keep together: parser construction + output formatting + exit codes
  move: confirm/promote mapping and --confirm refusal                -> KnowledgeService
        applied -> submit routing, reconcile AND-rule                 -> application layer
        generic_reconcile                                            -> one shared integrity check

util.py  (53)
  keep: utc_now, sha256_text, sha256_file, canonical_json (used by all five layers)
  delete: slug, safe_relative_path (dead)
  leave in place: sha256_bytes, normalized_text (single consumer; churn exceeds benefit)
```

---

## 3. Target structure

```text
cv_engine/
  domain/
    models.py                 # unchanged - see section 5.1
    facts.py  profiles.py  presentations.py  candidate.py  knowledge.py
    analysis/
      __init__.py             # re-exports classify_job, merge_classification,
                              # unresolved_approval_reasons only
      classification.py       # PROFILE_TERMS/SALES_TERMS/TECH_TERMS/SELECTION_CONCEPTS,
                              # detect_language, scoring, track resolution, confidence
      gaps.py                 # the 5 gap rules + substitute fact IDs, derive_fit,
                              # merge_gaps, FIT_SEVERITY
      approval.py             # CONFIDENCE_APPROVAL_THRESHOLD,
                              # APPROVAL_RESOLVING_OVERRIDES, unresolved_*,
                              # merge_classification
    selection.py
    drafts.py                 # assembly + claim edits
    draft_markdown.py         # Markdown projection + round-trip codec
    validation.py
    recruitment.py            # NEW (stage 6): ApplicationStatus transition graph
    render_validation.py      # NEW (stage 8): Ready groups 4-10 over a RenderEvidence DTO
  application/
    services/
      __init__.py             # re-exports the 7 services (import paths unchanged)
      base.py  applications.py  analysis.py  drafts.py
      rendering.py  tracking.py  knowledge.py  projections.py
    commands.py  queries.py  ports.py  errors.py  chain.py  ready.py
  infrastructure/
    db.py  knowledge.py  canonical_data.py  artifacts.py
    legacy_source.py  providers.py  migration.py
    rendering.py              # mechanics only after stage 8
  runtime/
  cli.py
  util.py
```

Each new module earns its place by a distinct change trigger:

- `analysis/classification.py` changes when job-market phrasing or a Profile is added;
  `analysis/gaps.py` changes when the candidate's verified history or a requirement
  phrasing changes; `analysis/approval.py` changes when approval-safety policy or the AI
  proposal contract changes.
- `draft_markdown.py` changes when the Markdown marker format changes; `drafts.py`
  changes when claim or composite rules change.
- `recruitment.py` changes when the recruitment lifecycle changes — which is a domain
  decision per §3.1, not a persistence one.

**Deliberately not created**: `use_cases/` (would replace the approved §3.2 seams);
`shared/` (six real primitives remain after the dead ones go, and the architecture test
already whitelists `util` for the domain, making it a declared shared module rather than
an accident); `infrastructure/persistence|rendering|filesystem/` (eight flat modules is
not yet flat enough to hurt, and M2's §3.3 repository split is the boundary that will
justify `persistence/` — doing it now would mean doing it twice); `domain/models/` (see
5.1); `cli/` (see 5.6); `api/` and `frontend/` (M3 and M4 per the implementation plan).

---

## 4. Staged plan

Guardrails first, then mechanical moves, then anything that touches behaviour. Test
command: `./.venv/bin/python -m pytest -q`, with `CV_REQUIRE_BROWSER=1` for a complete
run — `tests/conftest.py:104-119` refuses to call a run complete without the browser
tests.

**Stage 0 — this document.** No code. Risk: none. *Done.*

**Stage 1 — guardrails, before any move.** Extend `tests/test_architecture.py` beyond
`("domain", "application")` to `infrastructure`, `runtime`, `cli.py`, and `compat.py`
with rules appropriate to each: the CLI must not import `infrastructure.db`; no library
module may import `subprocess`; no module outside `domain/` may define an
`ApplicationStatus` transition table. Land it with an explicit allowlist of the known
offenders (A2, A6, A24) so the file records the debt and blocks new instances. Fix A9 so
`tests/helpers.py` imports the production sealing rule. Add the missing tests for the
methods later stages will move (A25). Risk: **low** (test-only).

**Stage 2 — dead code.** Delete `util.slug` and `util.safe_relative_path`; drop the
unused `connect` import in `cli.py:13` and `sha256_bytes` in `migration.py:20`. Risk:
**low**. Path containment then has three live implementations with differing symlink
semantics (A23), to be unified in M2.

**Stage 3 — `application/services.py` → `application/services/` package.** One module
per service plus `base.py`; `__init__.py` re-exports all seven so
`from ..application.services import DraftService` keeps resolving. Affected:
`runtime/composition.py:16-22`, `cli.py`, `compat.py`,
`tests/test_application_contracts.py:37,251`. Note that
`tests/test_application_contracts.py:253` calls `inspect.getsource(DraftService.draft)` —
unaffected by a file move, but re-run it explicitly. Risk: **low** (pure move).

**Stage 4 — `domain/analysis.py` → `domain/analysis/` package**, three modules per
section 3. The three-symbol public surface makes this safe: `__init__.py` re-exports
exactly those three, so `services.py:6` and `validation.py:5` do not change. Tests:
`tests/test_analysis.py tests/test_classification_policy.py tests/test_selection.py
tests/test_golden.py`, then the full suite. Risk: **low**.

**Stage 5 — `domain/draft_markdown.py`.** Move the Markdown codec out of `drafts.py`,
keeping `CLAIM_MARKER` with the codec — it has a single owner today and must keep one.
Affected: `domain/validation.py:6`, `application/services.py:7-12`,
`infrastructure/artifacts.py`, `tests/test_drafts_validation.py`, `tests/test_golden.py`.
Risk: **low-medium** (imports fan out further than stage 4).

**Stage 6 — `domain/recruitment.py`.** Move `ALLOWED_TRANSITIONS` and the transition
predicate out of `infrastructure/db.py:211-225,504-538`; `db.transition_status` keeps
raising and simply asks the domain what is allowed. Leave `save_analysis`'s post-commit
orchestration alone in this stage. Exception types and message text must be preserved
byte-for-byte, because tests match on them. Risk: **medium** (touches the status
machine).

**Stage 7 — requires explicit approval before starting: unify `ValidationReport`
construction (A1).** One domain factory applying the `hard` rule, used by
`validation.py`, `ready.py`, and render validation, plus disambiguation of the two
`"filename"` groups. This changes validation behaviour and the persisted
`validation_runs.report_json` key set: historical rows keep the old keys while new rows
get the new ones. `CLAUDE.md` forbids changing validation behaviour silently and requires
migration safety for stored shapes, so the options (rename versus keep both group names;
back-fill versus version the report shape) must be presented before any code is written.

**Stage 8 — M2-aligned; not started now.** Sequenced with the §3.3 repository split so
the work happens once: move Ready groups 4–10 into `domain/render_validation.py` behind a
typed `RenderEvidence` DTO (A4) — note this breaks the monkeypatch targets at
`tests/conftest.py:331-332` and the `POLICY_MODULES` list at
`tests/test_candidate.py:22-33`; move the `_set_ready`, `_record_submission`, and
`record_decision` rules plus `save_analysis`'s orchestration out of `db.py` (A2); give
the decision record a typed shape (A5); move the confirm/promote rule from `cli.py` into
`KnowledgeService` (A6); collapse the four artifact-integrity copies (A7); retire
`compat.Engine` and re-point the `conftest.py` fixtures at the services (A8); resolve
default emphasis from the Profile store (A3); unify path containment (A23); remove the
`subprocess` pytest call (A24).

---

## 5. What will not be split, and why

**5.1 — `domain/models.py` (524 lines).** It is the hub: imported by fifteen modules,
with dense and legitimate cross-group references (`DraftDocument` holds `Track`,
`ProfileName`, `Emphasis`, and `SelectionManifest`; `JobAnalysis` holds `FitLevel` and
`Gap`). It was *deliberately consolidated* at `a68bcec` ("Simplify domain model
organization") and hardened with contract tests in the same commit. Splitting buys no
discoverability and creates a new import-order surface. The only justified micro-move is
`ProviderContext` and `ProviderTaskResult` → `infrastructure/providers.py` (A21), and
even that can wait for M2's provider work.

**5.2 — `infrastructure/migration.py` (839 lines).** Cohesive around one bounded,
one-time concern, read as a unit, and bound to a frozen evidence artifact
(`docs/v1-retrospective-migration-verification.json`). Live cutover has not happened and
`CLAUDE.md` forbids casual changes to migration safety. Fix only the two real defects
(A9, A24); do not restructure it.

**5.3 — `domain/selection.py` (447 lines).** One policy: ranked fact selection under
budgets, role-block floors, and pins. The four-tuple rank (`:113-124`), `_role_blocks`,
and `_block_floor_picks` must be read together to be correct.

**5.4 — `domain/validation.py`'s 280-line function.** Genuinely twelve policies (A13),
but they share one accumulating `groups`/`issues` state and one traversal of the draft.
Splitting it before stage 7 settles who owns `ValidationReport` construction would mean
splitting it twice. Revisit after stage 7.

**5.5 — the checks `validation.py` appears to duplicate from model validators.**
`misplaced-headline-claim` (`validation.py:84-92`) looks redundant against
`DraftDocument.validate_headline_placement` (`models.py:475-480`), but it is not:
`StrictModel` sets `validate_assignment=True`, so `draft.headline = x` revalidates, while
`drafts._replace_claim:317-320` mutating `section.claims[index]` in place does not. The
same applies to the deliberate coverage recomputation — `validation.py:63-65` states that
it refuses to trust the manifest because *"the manifest travels in an editable working
file"*. Keep both; add a cross-reference comment rather than merging.

**5.6 — no `cli/` package yet.** The 200-line `elif` chain in `main` is a symptom of the
policy that should not be there (A6), not of the file. Extract the policy; split the
package when `api/` arrives in M3 and the two clients need shared resolvers.

**5.7 — no `shared/` package.** After stage 2 there are six real primitives.
`sha256_bytes` and `normalized_text` have one consumer each and could move next to their
callers, but the churn exceeds the benefit while `utc_now`, `sha256_text`, `sha256_file`,
and `canonical_json` legitimately span every layer.

**5.8 — no `infrastructure/` subpackages yet.** Eight flat modules with distinct names.
The boundary that will justify `persistence/` is M2's split of the single `Repository`
into the seven repositories named in §3.3.

---

## 6. Verification contract for the staged work

- After each of stages 1–6: the stage's own test subset first, then
  `./.venv/bin/python -m pytest -q` clean.
- At the end of the mechanical stages:
  `CV_REQUIRE_BROWSER=1 ./.venv/bin/python -m pytest -q`.
- `tests/test_architecture.py` must pass with its widened scope, and its allowlist must
  shrink — never grow — across stages.
- `tests/test_golden.py` is the semantic-parity check required by
  `docs/v2-test-and-acceptance-plan.md` §3 (selected facts, rendered claims, validation
  outcomes, Ready eligibility, decision behaviour). It must report **no** semantic
  difference after every stage; any difference means a move described as mechanical was
  not.
- End to end through the CLI against the isolated development Workspace, never live v1
  data: `cv workspace status`, then ingest → analyze → draft → validate → approve →
  render → `cv ready <id>` → `cv reconcile`, confirming Ready is still reached with no AI
  key.
- One commit per stage at a stable boundary, no mixing. Stages 7 and 8 do not begin
  without an explicit decision.

---

## 7. Waves 0–2 execution record

Stages 1–6 landed as behavior-preserving boundary changes on 2026-08-18. The three
parallel Stage 3–6 lanes were based on the same guarded Wave 0 code, kept exclusive file
ownership, and were integrated in the required A → B → C order.

| Stage | Result | Scoped commit/evidence |
| --- | --- | --- |
| 1 — guardrails | Passed | `ee0ea29`; `tests/test_architecture.py` covers the outer-layer debt, `tests/helpers.py` uses the production report seal, and application move surfaces have direct service tests. `0f0bc86` made the existing candidate-literal guard follow either the service module or package after that exact path dependency was exposed by Stage 3. |
| 2 — dead code | Passed | `7922def`; removed only `slug`, `safe_relative_path`, and the two audited unused imports. Architecture/golden subset: 3 passed; full suite: 113 passed. |
| 3 — application services | Passed | `4a92821`; split into the approved focused service modules. Lane gate: 29 passed; lane full suite: 113 passed. |
| 4 — analysis policy | Passed | `a1e10e8`; split classification, gaps, and approval policy. Stage subset: 21 passed; full suite: 113 passed. |
| 5 — Markdown codec | Passed | `d9ea7ab`; `draft_markdown.py` owns the projection/round-trip codec and marker. Lane gate: 17 passed; lane full suite: 113 passed. |
| 6 — recruitment transitions | Passed | `08457db`; the transition graph/predicate moved to `domain/recruitment.py`, while repository exception types and messages remained unchanged. Final lane subset: 23 passed; full suite: 113 passed. |

Integration removed every temporary re-export and repointed callers to the owning
modules. After each merge, the lane subset and the full 113-test suite passed. The
combined Wave 2 boundary subset passed 54 tests. Final verification passed:

- `CV_REQUIRE_BROWSER=1 ... -m pytest -q`: 113 passed, including the real browser,
  rendering, PDF, ATS, and golden parity coverage.
- `tests/test_golden.py`: no semantic difference in selected facts, rendered claims,
  validation outcomes, Ready eligibility, or decision behavior.
- Fresh isolated Workspace (`purpose=development`, `data_class=copy`) with no AI key:
  workspace status → ingest → deterministic analyze → draft → validate → approve →
  render → Ready → reconcile all passed. The PDF was one page with ATS claim coverage
  `1.0`; Ready integrity and reconciliation both reported `passed=true`.

No threshold, message string, exception type, validation-group name, status, public
signature, stored report shape, artifact path policy, or fact semantic changed.

### Remaining work and residual allowlist debt

- **Stage 7 remains approval-gated and was not started.** `ValidationReport`
  construction, group naming, and stored report-shape decisions remain exactly as they
  were at the audit baseline.
- **Stage 8 remains deferred to M2 and was not started.** This includes render/Ready
  policy extraction, the remaining READY-demotion and persistence orchestration from
  A2, decision-record typing, CLI policy removal, artifact-integrity consolidation,
  compatibility-façade retirement, Profile-backed default emphasis, path-containment
  unification, and removal of the migration-time pytest subprocess.
- The Stage 1 allowlist shrank from three entries to two. The removed entry is the
  infrastructure-owned `ApplicationStatus` transition table resolved by Stage 6. The
  two explicit residual entries are `cli.py` importing `infrastructure.db` (A6) and
  `infrastructure/migration.py` importing `subprocess` (A24); both belong to Stage 8.
