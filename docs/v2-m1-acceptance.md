# M1 Acceptance — Application Foundation

Status: **Checklist met — awaiting re-review** (2026-08-17)

Milestone: `docs/v2-implementation-plan.md` section 3 (M1 — Application foundation)

Baseline: `v1.0.0` / `2cc31c7`, 131 tests passing with `CV_REQUIRE_BROWSER=1`

This file replaces both earlier records: the implementation report that declared M1
`Passed` and the review report (`docs/v2-m1-acceptance-report.md`) that declared it
`CHANGES REQUIRED`. The first was premature — it reported a suite result that the
review then showed was not isolated from the v1 worktree, so its test evidence could
not support the claim it made. Keeping two contradictory records would leave the
milestone's status a matter of which file a reader opened first.

Two review rounds have run against this milestone. The first found eight items, closed
in section 2. The second found four more (section 3) and did not accept M1: three were
architectural gaps this record had either not detected or had re-scoped without
approval. Those are now closed, and this file records both what was wrong and what the
earlier version of it got wrong.

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

Now: `application/commands.py` carries the command inputs and results, and services
return them instead of tuples and bare dicts; `application/errors.py` defines
`ApplicationError` with `UnknownRecord`, `StateConflict`, `ValidationBlocked` (carrying
its report), `LineageBroken`, `KnowledgeRejected`, and `DependencyUnavailable`;
`ApplicationRepository` is composed from `ApplicationStore`, `JobStore`,
`ArtifactRegistry`, and `FactAudit`, and exposes no path, connection, or private method;
`UnitOfWork` is declared and implemented over the adapter's existing transaction.

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

## 4. Checklist evidence

### Domain/application code imports no FastAPI, SQLite, path layout, or provider HTTP

`tests/test_architecture.py::test_domain_and_application_dependencies_point_inward`
enforces this on the source itself rather than by review. Over both layers it reports:

- no `sqlite3`, `fastapi`, `playwright`, `urllib`, `uvicorn`, `httpx`, or `requests`
  import;
- no outward internal import — domain may name only domain and shared primitives, and
  application only domain, application, and `util`, so neither can reach the runtime,
  the composition root, or an infrastructure adapter. The v1 compatibility façade lives
  outside the layered packages (`cv_engine/compat.py`) precisely so it can build
  services without dragging that dependency into application code;
- no filesystem call — no read, write, open, listing, or directory creation;
- no path composed from a string literal, and no mention of `artifacts_root`,
  `knowledge_root`, or `base_dir`.

It is one test rather than five so the whole boundary is stated once and a violation is
reported with every other violation beside it.

`cv_engine/application/ports.py` defines `ApplicationRepository` — composed from
`ApplicationStore`, `JobStore`, `ArtifactRegistry`, and `FactAudit` — plus `UnitOfWork`,
`ArtifactStore`, `KnowledgeStore`, `Renderer`, and `ClassificationProvider`.
`cv_engine/runtime/composition.py` is the only module that binds them to `Repository`,
`FilesystemArtifactStore`, `FileKnowledge`, `PlaywrightRenderer`, and
`OpenAIClassificationProvider`.

### The CLI completes the deterministic v1 Definition of Done through the services

Re-run after the second round's changes, in a fresh isolated Workspace
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

Every command is dispatched to an application service; only the chained `cv fast` flow
goes through the façade.

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

`tests/test_workspace.py` covers:

- missing marker, unreadable marker, unknown workspace version, second marker;
- a legacy v1 root refused for both load and init, with no marker written into it, and
  with no override parameter left in the production API;
- live data refused under a development or test purpose, both at creation and on load;
- declared roots confined to the Workspace, enforced at creation and against a
  hand-edited marker;
- `LegacyV1Source`: inventory leaves the source byte-identical, reads are bound to the
  inventory hash and fail when the source changes mid-run, traversal and absolute paths
  are refused, a marked Workspace is not accepted as a legacy source, and the SQLite
  connection is opened read-only (writes raise `sqlite3.OperationalError`);
- CLI: `workspace init`/`status`, refusal of a normal command against an unmarked root,
  and `workspace inventory-legacy` leaving the source unmarked.

The engine reaches its data only through `load_workspace`, so this decision is made in
one place.

### All applicable v1 tests pass

```text
CV_REQUIRE_BROWSER=1 python -m pytest -q  ->  209 passed in 123.25s
```

131 tests at the v1 baseline, 209 now. No v1 coverage was removed. The added tests cover
the Workspace layer, the candidate context, the architectural boundary, the
cross-worktree module guard, the fact `link_target` invariant, and — new in this round —
the application layer's declared contracts in `tests/test_application_contracts.py`:
result types, the error taxonomy, the focused ports and their absence of adapter
internals, the UnitOfWork's commit and rollback, explicit source IDs, and the rule that
no command resolves its own source.

Two earlier runs are worth recording, because this file previously reported one of them
as if it settled the item:

- `187 passed, 1 failed` — the first isolated run. The failure was a stale test
  reference to the renamed identity fact, not a defect in the code under test. This file
  then reported it as "187/188 confirmed plus one file confirmed separately", which is
  not a clean run and was correctly refused as evidence.
- `188 passed` — the independent clean run performed during the second review round,
  before the changes in section 3.

The 209 figure supersedes both and is the run that stands behind this record.

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
  implemented, wired into the composition root, and tested, which is what plan §3.2
  asks for. No command's writes were regrouped behind it, because that would change
  durability semantics and M1 requires v1 parity. `approve` still writes its two
  artifact versions and its decision record in three transactions, as v1 did. This is
  stated as a limit of the step, not as a deferral of the item.
- `migrate verify-live` has not been re-run — see section 5. That is the one piece of
  confirming evidence this record cannot produce from this worktree.
- `cv fast` is retained as the CLI compatibility flow and is documented in code as an
  explicit user approval instruction; it chains the same use-cases and cannot bypass
  validation or a blocker. It is the only remaining caller of the `Engine` façade.
- `Engine` still exists as a delegating façade for the v1 test suite, now at
  `cv_engine/compat.py`, outside the layered packages. It holds no business logic; it
  unwraps the new result types into the v1 shapes and resolves `latest` for the v1
  signatures that carry no source ID. It is removed once its callers address the
  services directly.
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
