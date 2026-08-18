# M1 Acceptance — Application Foundation

Status: **M1 closed — all six acceptance criteria passed** (2026-08-18)

Milestone: `docs/v2-implementation-plan.md` section 3 (M1 — Application foundation)

Baseline: `v1.0.0` / `2cc31c7`, 131 tests passing with `CV_REQUIRE_BROWSER=1`

This file replaces both earlier records: the implementation report that declared M1
`Passed` and the review report (`docs/v2-m1-acceptance-report.md`) that declared it
`CHANGES REQUIRED`. The first was premature — it reported a suite result that the
review then showed was not isolated from the v1 worktree, so its test evidence could
not support the claim it made. Keeping two contradictory records would leave the
milestone's status a matter of which file a reader opened first.

Four review rounds have run against this milestone. The first found eight items,
closed in section 2. The second found four more (section 3) and did not accept M1:
three were architectural gaps this record had either not detected or had re-scoped
without approval. A third boundary audit then found that the declared application
contracts were still not the contracts clients actually used. Those gaps are also
closed in 3.5. The fourth review found remaining M1 work in `cv fast`, the obsolete
migration CLI, and gap-fact identity coverage, then over-scoped a separate containment
audit. Section 3.6 records the resolution and the exact boundary of criterion 5.

## 1. Commits in this milestone

| Commit | Scope |
| --- | --- |
| `63a133d` | Workspace model, marker, roots, IDs, fail-closed guards, read-only v1 source adapter, configuration precedence |
| `1846578` | CandidateContext; candidate literals removed from drafting, rendering, filename, and link validation |
| `4e522ed` | Isolated development Workspace kept out of version control |
| `0f899fd` | domain / application / infrastructure separation |
| `2666ed6` | Application services behind ports, composition root, CLI on services, versioned export, architecture tests |
| `3bba708` | First review round closed: cross-worktree import, artifact-location port, declared repository operations, fact ID and link source-of-truth |
| `fd540f1` | The two contradictory acceptance records merged into this one |
| `c7150ff` | File access moved out of the domain and application layers |
| `0b720f2` | Command/query DTOs, error taxonomy, focused repository ports, UnitOfWork |
| `85aa841` | Explicit source IDs in commands; `latest` resolution in the compatibility layer |
| `a755ee0` | Application contracts made load-bearing: Pydantic DTOs, read projections, focused service ports, stable failures, explicit-commit UnitOfWork |
| `87df714` | Consolidated duplicated tests without dropping invariant coverage |
| `efa67ae` | Recorded the third boundary remediation and its evidence |
| `a68bcec` | Consolidated the domain models with direct invariant tests |
| `62852d5` | Audited `cv_engine` responsibilities and established the staged boundary plan |
| `ee0ea29` | Added outer-layer architecture guardrails and characterization coverage |
| `7922def` | Removed only the dead utilities and imports established by the audit |
| `0f0bc86` | Made the candidate-policy guard follow the services package move |
| `4a92821` | Split application services into their approved package seams |
| `a1e10e8` | Split analysis policy into classification, gaps, and approval modules |
| `d9ea7ab` | Moved the Markdown codec to `domain/draft_markdown.py` |
| `08457db` | Moved recruitment transition policy into the domain |
| `8c5f349` | Removed temporary re-exports and finalized direct owning-module imports |
| `11b9d95` | Corrected interpreter evidence and recorded the Stage 7 options |
| `a974f4b` | Added the domain-owned `ValidationReport` factory and construction guard |
| `3896ee1` | Retired the obsolete writable pre-v1→v1 migration CLI surface |
| `d34cf50` | Moved `cv fast` orchestration into the CLI and removed `Engine` |
| `67a80d5` | Guarded all nine gap-policy substitute fact IDs against the canonical store |

## 2. First review round, and its resolution

Eight findings. Seven were closed at the time; one was re-scoped, wrongly — see 3.3.

### 2.1 A v2 module was loading v1 code — closed

`cv_engine/runtime/workspace.py` still imported `..models`, a module that stopped
existing at `0f899fd`. The v1 worktree's editable install
(`__editable__.multi_track_cv-1.0.0.pth`) resolves any `cv_engine` submodule missing
here to the v1 tree, so the import silently succeeded against
`/Users/matanmalka/Projects/resume_python/cv_engine/models.py`.

The import now names `..domain.models`. Walking every loaded module found exactly one
foreign module, `cv_engine.models`, and `cv_engine.__path__` is v2-only, so nothing
else fell through. The contaminated symbol was `StrictModel`, reached only as
`WorkspaceMarker`'s base class, and the two worktrees' copies are byte-identical — no
behaviour differed. That is a reason the conclusions held, not a reason the evidence
was clean, so the suite was re-run.

The old guard checked `cv_engine.__file__`, which was correctly v2, and therefore could
not see a submodule-level fallback. `tests/conftest.py` now checks **every** loaded
`cv_engine.*` module, at import and again in `pytest_sessionfinish`, because modules
load lazily and a stale import on a rarely exercised path would otherwise surface only
as a mysteriously passing test.

### 2.2 The application layer composed its own path layout — closed

`services.py` assembled `artifacts_root/"working"/<id>` and `artifacts_root/<id>/v###`,
called `mkdir` and `shutil.copy2`, and `ready.py` resolved `workspace.root / path`. The
M1 checklist names "no path layout" explicitly, and `tests/test_architecture.py`
whitelisted `application -> runtime` — the test encoded the exception instead of
enforcing the rule.

`ArtifactStore` (`application/ports.py`) is now the port the application asks for a
location through, and `FilesystemArtifactStore` (`infrastructure/artifacts.py`) is the
one module that decides directory names. The architecture test dropped the whitelist and
gained a check for `artifacts_root`, `"working"`, and `mkdir(` in the application layer.

That check was too narrow and this fix was incomplete: the layout it removed from the
application layer was already present in the domain, and looking for three strings in
one layer could not see it. Both were corrected in the second round — see 3.1.

### 2.3 Parity was unverified — closed

The finding was valid but overstated: the golden and parity path imports
`cv_engine.domain.models` throughout, and the fallback reached only `WorkspaceMarker`'s
base class. The parity conclusion stood on its merits. It has been re-established on a
clean run regardless — see section 4.

### 2.4 A new v2 fact carried a semantic ID — closed

Product spec §17, architecture §5, and migration §6.1 all require UUIDv4 for facts
created in v2; semantic IDs are preserved only where a v1 fact ID actually exists to
preserve. The candidate identity fact was created as `common.identity.name`. It now
carries `0f3a6c4e-6b5f-4a2b-9c1d-7e8f5a0b2c31`, in `base/common.md`,
`base/candidate.json`, and `infrastructure/canonical_data.py`.
`tests/test_facts_profiles.py` asserts the ID parses as a UUID rather than hardcoding
it.

### 2.5 The contact URL lived in two places — closed, by a different remedy

`base/candidate.json` duplicated the LinkedIn and GitHub URLs that the canonical facts'
`meaning` already states in prose.

The review's suggested fix — derive the target from the canonical rendering — is wrong
and was not applied. The rendering is display text, `linkedin.com/in/matanmalka1`;
deriving from it yields `https://linkedin.com/in/...`, dropping `www.`, changing the
href the recruiter follows and breaking link validation.

The address is instead a machine-readable field on the fact itself:

- `Fact.link_target` holds the absolute address, with a model validator requiring
  `https://` and requiring the target to carry the fact's own English rendering, so a
  fact cannot display one profile and link to another.
- `CandidateContext.link_targets` became a resolved projection, like `names`, populated
  from the facts at load time.
- `base/candidate.json` no longer declares it, and `load_candidate_context` refuses a
  file that declares any resolved field, so an old copy fails loudly instead of being
  silently overwritten.

`link_target` restates, machine-readably, what the migrated fact's `meaning` already
said. No fact was strengthened. It was added to the generated sources in
`canonical_data.py` as well as to the live `base/common.md`, so a re-run migration
produces the same records — see section 5.

### 2.6 `latest` resolution inside commands — re-scoped to M3, wrongly; now closed

This record previously argued that "commands use explicit source IDs" is an M3
acceptance item (plan §5.4) and not an M1 one, and left it open on that basis. That was
wrong, and it was wrong in this file's favour. See 3.3 for the contradicting text and
the fix.

### 2.7 Services called private repository methods — closed

`_set_ready` and `_record_submission` were called from services but declared on no port.
`set_ready` and `record_submission` are now declared operations on the
`ApplicationRepository` protocol and on `Repository`; each delegates to the persistence
primitive below it, which still re-derives its proof from database state rather than
trusting the caller.

### 2.8 The `acknowledge_legacy_root` escape hatch — closed

Its only caller was a test fixture. The parameter is gone from `create_workspace`, and
`tests/conftest.py` writes the marker itself for the one fixture that models a root the
legacy in-place migration already converted. Production code has no override that can
mark a legacy root.

## 3. Second review round, and its resolution

Four findings. M1 was not accepted on them. All four were valid; two were misjudgements
recorded in the previous version of this file rather than defects the review introduced.

### 3.1 The filesystem boundary was still not clean — closed

The domain composed and opened its own storage: `base/candidate.json`
(`domain/candidate.py`), `profiles/**/*.yaml` including writes (`domain/profiles.py`),
`config/emphasis.json` (`domain/selection.py`), `rendering/rules/presentations.json`
(`domain/presentations.py`), and `working/<application_id>` with a direct write
(`domain/drafts.py`). `application/services.py` loaded and wrote knowledge through paths
and those domain functions.

This is the same finding as 2.2, and 2.2's fix was incomplete: introducing `ArtifactStore`
moved layout out of the application layer, and it landed one level down in the domain,
where the same storage knowledge was just as wrong. The check added with it looked for
three known strings in one layer, so it could not see that.

The stores now take parsed documents — `FactStore.from_sources`,
`ProfileStore.from_documents`, `EmphasisPolicyStore.from_payload`,
`PresentationStore.from_payload`, `build_candidate_context` — and `seal_draft` returns
the payloads a stored draft consists of with its content hash bound to the Markdown.
`validate_draft` and `synchronize_markdown_claims` take the document's text.
`infrastructure/knowledge.py` and `FilesystemArtifactStore` are the only modules that
know where anything lives, both reached through ports.

`tests/test_architecture.py` is rewritten around the rule instead of around known
strings, and states the whole boundary as one contract,
`test_domain_and_application_dependencies_point_inward`: over both layers it reports
forbidden external imports, outward internal imports, any filesystem call, any path
composed from a string literal, and any mention of a storage root. The layout check
matches on the syntax tree — a name divided by a string literal — so `rsplit("/")` and
`https://` are not mistaken for path composition.

### 3.2 The application layer's contracts were not defined — closed

Plan §3.2 assigns "Define application command/query DTOs and stable error types" and
"Define focused repository ports and UnitOfWork" to M1. The previous version of this
file listed UnitOfWork as deferred to M2 under "Deviations", which is a scope change
nobody approved, and did not mention DTOs or error types at all. `ApplicationRepository`
was one broad port that also exposed `path: Path`.

Now: `application/commands.py` carries Pydantic command and result DTOs, and
`application/queries.py` carries purpose-built read projections. Application results
name records by stable IDs and do not expose filesystem locations, database rows, or
serialized database columns. `application/errors.py` defines `ApplicationError` with
`UnknownRecord`, `StateConflict`, `PreconditionFailed`, `ValidationBlocked` (carrying
its report), `LineageBroken`, `KnowledgeRejected`, `DependencyUnavailable`, and
`InfrastructureFailure`. Expected missing-record, knowledge, provider, renderer, and
filesystem failures are normalized at the boundary.

Services are typed against the port they use (`ApplicationStore`,
`PreparationRepository`, `DraftRepository`, `ReadinessRepository`,
`TrackingRepository`, `KnowledgeAuditRepository`, or `QueryRepository`), not the
composition-root repository. CLI list/show/versions/decision and recruitment mutations
now go through query/application services rather than reading or mutating SQLite rows.
`ApplicationRepository` remains only the composition-root view of the single SQLite
adapter and exposes no path, connection, or private method.

`UnitOfWork` is declared and implemented as an explicit-commit transaction: exception,
explicit rollback, and normal exit without `commit()` all roll back. The boundary is
not yet used to regroup v1 commands; that deliberate M1 limit is recorded in section 6.

`WorkflowError` stays bound to `ApplicationError`, so the v1 CLI and test suite catch
exactly what they caught before. `tests/test_application_contracts.py` holds all of it.

**Stated deliberately:** no command's transaction grouping changed. `approve` still
writes its two artifact versions and its decision record through three separate
transactions, as v1 did. Regrouping them behind the new boundary would change durability
semantics, and M1 requires v1 parity, so the boundary is defined, wired, and tested
without any write being moved behind it. That is a smaller step than the plan's wording
could be read to require, and it is recorded here rather than presented as complete.

### 3.3 Commands still resolved `latest` — closed, and 2.6 was wrong

`AnalysisService.analyze` selected `latest_snapshot` and `DraftService.draft` selected
`latest_analysis`. This record had re-scoped that to M3 by citing plan §5.4 alone. Two
texts contradict that reading and neither was addressed:

- Architecture §8: "Commands always receive explicit source IDs. `latest` belongs to
  query/UI convenience, not command semantics."
- Plan §3.3, an M1 bullet: "Add compatibility resolvers/warnings only where legacy CLI
  signatures omit an explicit v2 source ID."

`analyze` now takes `job_snapshot_id` and `draft` takes `job_analysis_id`, and each
refuses a source belonging to another application. `resolve_job_snapshot_id` and
`resolve_job_analysis_id` live in `compat.py`, which is where a v1 signature that
carries no source ID is served. The CLI gained `--job-snapshot` and `--job-analysis`, so
the v2 contract is reachable without the legacy path.

`draft` still reads the newest snapshot, but as a staleness check on the analysis the
caller named rather than to choose a source.
`test_no_command_resolves_its_own_source` pins that: `latest_analysis` may not appear in
the service at all, and `latest_snapshot` exactly once.

### 3.4 This record was out of date — closed

It reported 187/188 and a conditional status after a clean 188/188 run existed, and did
not carry 3.1–3.3 as blockers. Section 4 now reports the current run, and the three gaps
are recorded above as what they were: blockers, two of them created by this file's own
earlier judgements.

### 3.5 The application contracts were declared but not load-bearing — closed

The third audit read production code independently of the test refactor and found four
remaining gaps behind 3.2's earlier claim:

- command/result classes were dataclasses, results still returned `Path`, and there
  were no query DTOs;
- the focused repository protocols were nominal while every service and several CLI
  business commands still used the broad repository directly;
- expected `KeyError`, `FileNotFoundError`, provider, renderer, and knowledge failures
  could cross the application boundary outside the declared taxonomy;
- `SqliteUnitOfWork` committed any exception-free scope, so a forgotten explicit
  commit published state rather than rolling it back.

Commit `a755ee0` closes those gaps. Pydantic boundary DTOs are now the actual service
inputs and outputs; filesystem paths are resolved only by CLI compatibility or
infrastructure code; read projections strip `path`, `*_json`, and persistence-only
payloads; each service is parameterized by its focused port; normal CLI queries and
tracking mutations call services; expected failures use the application taxonomy; and
UnitOfWork requires `commit()`. The temporary compatibility façade continued converting
v2 models to v1 test shapes at that boundary; section 3.6 records its later removal
once those consumers moved to the services.

### 3.6 Fourth review: remaining M1 surfaces and acceptance scope — closed

The fourth review found three M1 items that the prior record still understated:

- `Engine.fast` owned a six-use-case orchestration and both validation gates even though
  plan §3.3 assigns that orchestration to the CLI;
- the obsolete pre-v1→v1 `cv migrate inventory|snapshot|test|dry-run|apply|reconcile`
  commands bypassed the Workspace guard and wrote into their selected source; and
- the nine canonical substitute fact IDs in gap policy had no existence guard.

Commits `3896ee1`, `d34cf50`, and `67a80d5` close those items. The writable migration
commands are no longer exposed, the two retained historical verification commands are
behind `load_workspace`, `cv fast` owns the exact orchestration in `cli.py`, every
workflow fixture calls services directly, the `Engine` class is gone, and `compat.py`
contains only the two sanctioned legacy source-ID resolvers.

The read-only reviewer then found four additional path/configuration issues and
recommended withholding M1 closure despite reporting all six §3.4 criteria as passing.
That conclusion used a broader proposed rule — that no CLI path may read or write any
unmarked or outside path — rather than criterion 5's actual marker-and-inventory
contract. The broader rule was withdrawn. The findings themselves are valid and are
recorded as A26–A29 in `docs/v2-architecture-audit.md`, with explicit M2 homes. This
record therefore disagrees with the reviewer's overall stop recommendation while
accepting its factual findings and its **6/6 PASS** assessment of the approved criteria.

## 4. Checklist evidence

All closure evidence below used the dedicated v2 environment at
`/Users/matanmalka/Projects/resume_python-v2/.venv/bin/python`, whose editable install
maps `cv_engine` to this worktree and whose Playwright-managed Chromium is installed.

```text
tests/test_integration.py tests/test_chain_integrity.py
tests/test_ready_integrity.py tests/test_fact_lifecycle.py       -> 35 passed
tests/test_workspace.py tests/test_migration.py
tests/test_architecture.py                                      -> 23 passed
tests/test_analysis.py                                          -> 6 passed
tests/test_golden.py                                            -> 1 passed
CV_REQUIRE_BROWSER=1 ./.venv/bin/python -m pytest -q            -> 124 passed
```

The independent read-only re-review reproduced the 23-test boundary gate, a 47-test
focused acceptance/golden gate, and the full 124-test browser-required suite.

### Domain/application code imports no FastAPI, SQLite, path layout, or provider HTTP

`tests/test_architecture.py::test_domain_and_application_dependencies_point_inward`
enforces this on the source itself rather than by review. Over both layers it reports:

- no `sqlite3`, `fastapi`, `playwright`, `urllib`, `uvicorn`, `httpx`, or `requests`
  import;
- no outward internal import — domain may name only domain and shared primitives, and
  application only domain, application, and `util`, so neither can reach the runtime,
  the composition root, or an infrastructure adapter;
- no filesystem call — no read, write, open, listing, or directory creation;
- no path composed from a string literal, and no mention of `artifacts_root`,
  `knowledge_root`, or `base_dir`.

It is one test rather than five so the whole boundary is stated once and a violation is
reported with every other violation beside it.

`cv_engine/application/ports.py` defines use-case-oriented repository ports and their
composition-root `ApplicationRepository`, plus `UnitOfWork`, `ArtifactStore`,
`KnowledgeStore`, `Renderer`, and `ClassificationProvider`.
`cv_engine/runtime/composition.py` is the only module that binds them to `Repository`,
`FilesystemArtifactStore`, `FileKnowledge`, `PlaywrightRenderer`, and
`OpenAIClassificationProvider`.

The same three-test architecture file also guards policy debt across infrastructure,
runtime, CLI, and compatibility code, and makes
`ValidationReport.from_findings` the only in-package report-construction authority.
The allowlist remains at two entries and did not grow.

### The CLI completes the deterministic v1 Definition of Done through the services

The explicit multi-command journey was historically re-run after the second round in
a fresh isolated Workspace
`.workspace/dev-m1` (`purpose=development`, `data_class=copy`), application
`e68a8753-9d16-4f14-8fc6-120a7c490de9`. Earlier journeys were left in place rather than
overwritten; each round used a new Workspace because the knowledge copy in the previous
one predates that round's changes.

This run uses the **explicit source IDs** from 3.3 rather than the legacy path, so the
v2 command contract is what the evidence exercises:

```text
cv workspace init --purpose development --data-class copy --knowledge-from .
cv init
cv ingest                        -> application e68a8753, job snapshot 98225363
cv analyze --job-snapshot 98225363 -> analysis 42d4e23f, sales / account-manager /
                                      account-growth, confidence 0.94, fit high
cv draft   --job-analysis 42d4e23f -> working draft, pre-render validation passed,
                                      29 claims / 28 facts
cv validate                      -> passed
cv approve                       -> v001 + decision record e51a5d52
cv render                        -> ready_validation.passed = true
cv ready                         -> passed
cv reconcile                     -> passed, 5 artifact versions, fact lifecycle passed,
                                    87 canonical facts
```

`cv render` reported all eight groups green (`render`, `page_count`, `pdf`, `ats`,
`links`, `visual`, `direction`, `filename`), one page, ATS claim coverage 1.0, and
produced `Matan Malka - Account Manager - CV.pdf`
(`38025eae7ee0e824442bdceef6227f58f9373fb67fb86c2ec138f36535a39cb5`). The rendered link
set was `tel:+972506688386`, `mailto:matan1391@gmail.com`,
`https://www.linkedin.com/in/matanmalka1` — the `www.` host preserved, which is the
concrete reason 2.5 did not derive targets from renderings.

Every command is dispatched to an application service.

After the third audit, the journey was repeated in a fresh temporary Workspace with
explicit snapshot and analysis IDs. `ingest -> analyze -> draft -> validate -> approve
-> render -> ready -> reconcile` passed; all six Ready-integrity groups were true, five
artifact versions were registered, and list/show/versions/decision plus next-action
updates succeeded through the new query and tracking services.

For final closure, `cv fast` was exercised through the real CLI in a fresh
`purpose=development`, `data_class=copy` Workspace with `OPENAI_API_KEY` removed. It
created application `99deab69-7d91-4a80-ae7b-016dbfb838db`, approved version 1, rendered
the recruiter-facing PDF, and returned `ready=true`. `tests/test_integration.py` pins
the exact ingest → analyze → draft → approve → render call order, both byte-identical
refusal messages, a CLI validation-refusal outcome, and the browser-backed CLI success
path. `Engine` has no production or test consumer because the class no longer exists;
`compat.py` now exports only `resolve_job_snapshot_id` and `resolve_job_analysis_id`.

### Selected facts, claims, validation outcomes, Ready eligibility, and decision behaviour retain semantic parity with v1

- The four golden fixtures (Development, Sales EN, Sales HE/RTL, Tech Sales) pass with
  their document body, selected fact IDs, sections, and rendered HTML hash unchanged
  from the v1.0.0 baseline.
- The only difference in generated Markdown across all four cases was the
  `fact_store_version` line in the provenance header, which moved because a canonical
  fact was added. Verified by generating each case with and without the new fact and
  diffing: every claim line, contact, section name, document name, and the HTML output
  were byte-identical.
- Golden fixtures pin `markdown_body_sha256` and assert the header's knowledge version
  against the live fact store, so a content change still fails while a legitimate
  knowledge version bump is checked rather than frozen.

### Candidate name is not hardcoded in core or renderer policy

`tests/test_candidate.py::test_policy_modules_contain_no_candidate_literal` scans ten
policy modules (`domain/drafts`, `domain/validation`, `domain/selection`,
`domain/presentations`, `domain/candidate`, `domain/profiles`, `domain/facts`,
`application/services`, `application/ready`, `infrastructure/rendering`) for
`Matan Malka`, `מתן מלכה`, `matanmalka1`, and `matan1391`. None remain.

Identity and contacts resolve from canonical facts through `CandidateContext`. The
identity fact was added to `base/common.md` through the normal lifecycle
(`source_version` 1.0.0 -> 1.0.1, 86 -> 87 canonical facts).

Remaining literals are in `infrastructure/canonical_data.py` (the v1 migration baseline)
and `infrastructure/migration.py` (a historical artifact path). Both are v1 evidence,
not policy.

### Normal v2 commands reject every missing, legacy, unknown, or unsafe marker; only the dedicated migration adapter can inventory an explicit v1 source read-only

This criterion guarantees two precise things:

1. every normal v2 command, including the two retained historical `migrate verify-*`
   commands, fails closed when its selected Workspace marker is missing, legacy,
   unknown-version, or an unsafe purpose/data-class combination; and
2. `LegacyV1Source` is the only path that **inventories** an explicit unmarked v1 source,
   binds that inventory by hash, and reads its SQLite database read-only.

`tests/test_workspace.py` exercises the four marker classes against a normal command
and both retained historical verifiers, checking that every selected root stays
byte-identical. It also proves that the six obsolete writable migration subcommands are
not exposed. The lower-level adapter tests cover inventory binding, mid-run source
change detection, traversal/absolute-path refusal, rejection of a marked Workspace, and
SQLite read-only enforcement.

The tick does **not** assert general path containment. The closing review found four
separate residuals, recorded as A26–A29: `--db`/`CV_DATABASE` can escape the Workspace
state root; default root subdirectories are vulnerable to post-creation symlink escape;
`workspace init --knowledge-from` can copy from an arbitrary unmarked or legacy source
without inventory binding; and Workspace config is read before marker validation.
Those are valid M2 deviations from architecture §§4/6.1, not failures of this criterion's
selected-marker and inventory guarantees.

### All applicable v1 safety invariants remain covered

```text
env CV_REQUIRE_BROWSER=1 ./.venv/bin/python -m pytest -q
-> 124 passed in 61.36s
```

The suite had grown from 131 tests at the v1 baseline to 209 during early M1, then was
consolidated to 102 by turning equivalent checklist variants into named matrices and
complete journeys. Closure collects 124 tests: the increase from the earlier 102-test
record is entirely added guardrail and behavior coverage, not restoration of duplicated
items. The four golden scenarios still run, and the suite covers Workspace isolation,
CandidateContext, the four-layer architecture boundary, cross-worktree imports,
fact/claim safety, application contracts, explicit source ownership, UnitOfWork
behavior, `ValidationReport` construction, Ready integrity, rendering/PDF/ATS, guarded
historical verification, `cv fast`, and the nine gap substitute identities.

This consolidation follows the risk-based rules in
`docs/v2-test-and-acceptance-plan.md`: required evidence is not a one-test-per-bullet
mandate, and individual legacy cases need not remain when a smaller test supplies the
same failure signal. No product, validation, migration, or artifact-lifecycle behavior
changed in this cleanup.

Two earlier runs are worth recording, because this file previously reported one of them
as if it settled the item:

- `187 passed, 1 failed` — the first isolated run. The failure was a stale test
  reference to the renamed identity fact, not a defect in the code under test. This file
  then reported it as "187/188 confirmed plus one file confirmed separately", which is
  not a clean run and was correctly refused as evidence.
- `188 passed` — the independent clean run performed during the second review round,
  before the changes in section 3.

The earlier 209-test and 102-test runs remain historical evidence. The 124-test
browser-required run above is the current closure evidence behind this record.

## 5. Migration safety note for `link_target`

`link_target` was added to the `common.contact.linkedin` and `common.contact.github`
records in both `infrastructure/canonical_data.py` and the live `base/common.md`, so
`_fact_source_baseline` compares equal records and reports no drift. Changing only one
of the two would have raised `migrated fact changed in base/common.md`.

Consequences to be aware of:

- The `canonical_fact_hashes` recorded in
  `docs/v1-retrospective-migration-verification.json` are a sealed record of a run at
  commit `9c965b8`. The live `common.md` hash already differed from it before this
  change, because the identity fact was added afterwards through the fact lifecycle.
  That file is point-in-time evidence, not a live invariant, and no test asserts those
  hashes.
- `migrate verify-live` has **not** been re-run against the local snapshot, because
  `data/snapshots/` is gitignored and not present in this worktree. The same code path
  is exercised by `tests/test_migration.py` against a synthetic legacy repository,
  including the "rewritten migrated fact" and "post-migration lifecycle fact" cases. A
  re-run of `migrate verify-live` on the machine holding the snapshot is the confirming
  evidence and has not been produced.

## 6. Deviations and open items

- **The UnitOfWork boundary is declared, not yet load-bearing.** It is defined,
  implemented with explicit-commit semantics, exposed by the repository, and tested
  for commit, exception rollback, and normal-exit rollback. No command's writes were
  regrouped behind it, because that would change durability semantics and M1 requires
  v1 parity. `approve` still writes its two artifact versions and its decision record
  in three transactions, as v1 did. M2 makes the boundary load-bearing for the new
  multi-record v2 commands; this is a staged activation, not a missing M1 contract.
- `migrate verify-live` has not been re-run — see section 5. That is the one piece of
  confirming evidence this record cannot produce from this worktree.
- `cv fast` is retained as the CLI compatibility flow and is documented in code as an
  explicit user approval instruction; it chains the same service use-cases and cannot
  bypass validation or a blocker. `Engine` has been removed. `compat.py` retains only
  the two source-ID resolvers sanctioned by plan §3.3/architecture §3.4.
- A26–A29 remain explicit M2 work: external database-root containment, default-root
  symlink containment, inventory-bound handling of legacy `--knowledge-from`, and
  marker-before-config ordering. Criterion 5 is intentionally narrower and does not
  certify these general path/configuration properties.
- No v2 command opened v1 live data at any point. Development used `.workspace/dev`,
  `.workspace/dev-rerun`, and `.workspace/dev-m1` (`purpose=development`,
  `data_class=copy`), each with its own knowledge copy.

## 7. What this record got wrong

Kept deliberately, because a status file that only ever records the code's mistakes is
not a reliable status file.

- It declared M1 `Passed` on a suite result that was not isolated from the v1 worktree.
- It re-scoped the explicit-source-ID requirement to M3 by citing the M3 checklist and
  not the two texts that place it in M1 (3.3).
- It listed the UnitOfWork as deferred to M2 under "Deviations", which was an
  unapproved scope change, and did not mention command/query DTOs or error types at all
  (3.2).
- It reported the filesystem boundary as closed when the fix had moved path composition
  from the application layer into the domain, and it added a test narrow enough not to
  notice (3.1).
- The fourth reviewer correctly reported all six §3.4 criteria as passing, but its
  recommendation to block M1 relied on an additional no-unmarked/outside-path criterion
  that was not part of §3.4 and was later withdrawn. The four underlying findings were
  retained as A26–A29 rather than being dismissed with the over-scoped bar.
