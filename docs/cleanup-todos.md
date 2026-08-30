# Cleanup todos — performance and architecture findings

Non-milestone cleanup items, tracked here so they do not compete with milestone scope in
the current tracker, `docs/m4-remaining.md`. Anything that becomes milestone work moves
there, or to `docs/m5-remaining.md` when it belongs to M5.

Execution rule: work serially. Complete and verify one item, then wait for explicit user
approval before starting the next. These items do not silently expand product semantics
or weaken an existing acceptance gate.

- [x] **TODO 1 — completed (`ab63ef6`):** added Ruff, defined the lint/format contract,
      removed dead/copied imports, and verified no behavioral change.
- [x] **TODO 2:** split the default fast non-browser pytest run from an explicit
      browser-complete gate.
- [x] **TODO 4 — completed (`c712aca`):** converted redundant CLI subprocess tests to
      in-process `cli.main(...)` calls while retaining the real process-boundary coverage.
- [x] **TODO 5 — completed (`fd12c20`):** split `cli.main()` into a stage-aware
      command-handler registry; CLI signatures, output, and errors unchanged.
- [x] **TODO 6 — completed (`9e82131`):** extracted `validate_draft` into ordered
      document and per-claim rule registries without changing validation behavior.
- [x] **TODO 7 — completed (`29d053b`):** removed the transitional composite repository;
      `Repository` now inherits the five ownership repositories, with boundaries and
      UnitOfWork behavior unchanged.
- [x] **TODO 8 — completed (`0b5a2c4`):** retired `persistence/primitives.py`; all random
      v2 identities now use the shared UUIDv4 policy in `util.new_id()`.
- [x] **TODO 9 — completed (`064465b`):** removed the unused serialization registry;
      versioning now begins only with a concrete payload schema and reader/writer.
- [x] **TODO 10 — completed (`73bb020`):** retired `compat.py`; omitted-source compatibility
      resolution now lives at the CLI boundary.
- [x] **TODO 11 — completed:** slimmed `ServiceBase` without replacing it with another
      abstraction. The three approved-payload helpers used only by `RenderingService`
      moved there as private methods; the unused `stored_draft`, `artifact_text`, and
      `task_contracts` helpers were removed. Provider-response preservation remains in
      the base because both analysis and draft services consume it. The change removed
      68 lines from the shared base, preserved behavior and error messages, and added no
      test items. Ruff, formatting, and diff checks passed in the agent session; the
      focused rendering regression and Class A non-browser gate passed in the user's
      environment.
- [x] **TODO 12:** enforce the existing ports with a type checker or propose a
      specification-compliant reduced port surface.
- [x] **TODO 13:** measured 178/201 MB dedicated virtualenvs and one shared 554 MB
      Playwright browser cache; with a warm `uv` cache, a 173 MB logical environment added
      about 2 MB physically while keeping independent editable environments and project state.
- [x] **TODO 14 — completed (`8429aa5`).** Every rule in `tests/test_architecture.py` was
      classified by what it actually proves. Two were hand-maintained and are now derived;
      the rest already read their answer out of the code and were left alone. Nothing was
      removed: no rule turned out to guard something that had gone away.

      The one that mattered was latent. The rule forbidding `domain`/`application` from
      naming a project root checked `artifacts_root`, `knowledge_root`, and `base_dir` —
      while the former path model defined five roots. `state_root`, `temp_root`, and
      `logs_root` were never covered. It now reads `ROOT_NAMES` from the module that owns
      them. Nothing violated the gap, which is exactly why nobody found it: a hand-kept
      list fails only when someone happens to trip the part that was written down.

      The two empty exception sets were deliberately kept rather than collapsed to a bare
      assertion, matching `CANDIDATE_EVIDENCE_MODULES` in `tests/test_candidate.py`. A
      re-introduced offender should fail at the designated place rather than arrive with
      an ad hoc exemption somewhere else.

- [x] **TODO 16 — completed (`bcd0fe4`).** `cli.py` (1,200 lines) is now `cv_engine/cli/`:
      eleven modules, largest 255 lines, plus `__main__.py` because a package needs one
      where a module got `python -m` for free. `__init__` re-exports the public surface,
      so no importer and no command name changed.

      A pure copy would have shipped a real bug. `_repo_root` computed
      `Path(__file__).resolve().parent.parent`, correct while `cli.py` sat directly in
      `cv_engine/`; one directory deeper it lands on `cv_engine/` instead of the repo
      root. The AST diff surfaced it as the only changed body, which is what that check
      is for — the ports split caught a dropped decorator the same way.

      Verified independently of the agent's report: 49 top-level names before and after
      with no unintended body change, and the full parser surface — 209 actions, flags,
      defaults, and `choices` — dumped from the old module loaded out of Git and diffed
      against the new one. Identical.

- [x] **TODO 17 — completed, but not as written.** The item assumed all four
      `operations.py` modules were misnamed. Checking each against its own package's
      naming convention rather than against the other three, only one was.

      | Module | Siblings named for | Verdict |
      | --- | --- | --- |
      | `application/operations.py` | the DTO family — `commands`, `queries`, `knowledge_mutations` | correct; it is the Operation contract |
      | `application/services/operations.py` | subject area — `analysis`, `drafts`, `rendering`, `tracking` | correct |
      | `infrastructure/persistence/operations.py` | the table it owns — `applications`, `artifacts`, `audit`, `tracking` | correct |
      | `runtime/operations.py` | role — `backup`, `composition`, `config`, `project` | **wrong**; renamed to `execution.py` |

      Renaming all four would have broken four internal conventions to fix one
      cross-package collision that no importer or traceback is actually ambiguous
      about: a relative `from .operations import` can only mean the sibling, and a
      traceback prints the full path. Only `runtime/` was named for what the module is
      about while its siblings are named for what they do. It holds
      `ForegroundOperationExecutor` and `OperationWorker` — the two hosts an Operation
      runs inside — so `execution.py` says what the others say.

      Two importers changed: `runtime/composition.py` and `tests/test_operations.py`.

- [x] **TODO 18 — completed:** audited the remaining files over 500 lines by subject,
      not by line count. The three files that held separable subjects were split as
      recorded below. A fresh `wc -l` scan still finds twelve files over the threshold,
      but none has a split that relieves coupling or creates a safer ownership seam:

      - `domain/models.py` (774) is the domain-model registry;
        `application/commands.py` (602) is the command/result DTO family.
      - `domain/selection.py` (611) owns selection; `application/state.py` (535) is one
        projection pipeline; and `domain/drafts.py` (553) is the pure draft-domain
        operation set. Splitting those by function would add module boundaries without
        separating state or collaborators.
      - `application/services/analysis.py` (585) keeps analysis and selection planning
        over the same Knowledge and repository boundary. They are distinguishable
        phases, but separating them would not remove a collaborator or a patch seam.
      - `infrastructure/persistence/operations.py` (641) is one Operation repository
        aggregate. It owns both `operations` and their resource-lease rows, so “one
        table” is not the reason to keep it together; their transactional lifecycle is.
      - `application/services/knowledge/service.py` (554) is the fact lifecycle and its
        reads after the two-phase mutation engine was extracted; and
        `application/services/operations/handlers.py` (502) is the already-separated
        Operation-handler half. A second size-only split in either would undo the subject
        boundaries the first split established.
      - `infrastructure/payloads.py` (525),
        `infrastructure/persistence/preparation.py` (515), and
        `infrastructure/knowledge.py` (505) respectively own immutable payload storage,
        the preparation repository boundary, and file-backed Knowledge. Each is one
        infrastructure subject.

      The threshold has therefore done its job as an audit trigger. Growth alone is not
      a defect, and no further split remains justified under this item.

      `application/services/drafts.py` is done. It was listed at 646 lines and had reached
      1412, holding eight subjects: generation, editing, validation, selection change,
      regeneration, archival, approval, and the decision export. It is now a package,
      `application/services/drafts/`, one module per subject over a shared
      `DraftServiceBase`, with `DraftService` assembled from them in `service.py`. No
      method body changed and the import path did not move.

      `application/services/knowledge.py` is done, and only the part that needed doing.
      The interesting cut was not "which command": lines 73-269 were a two-phase commit
      over Knowledge files plus SQLite - stage, prepare, activate, commit, mark, discard -
      with quarantine and crash recovery, written as private helpers of a command class,
      which is why nothing tested it directly. It is now
      `application/services/knowledge/mutations.py` (217 lines),
      `KnowledgeMutationEngine`, with the lifecycle commands and reads left in
      `service.py` (554). The import path did not move.

      It is a base class, not a collaborator the service holds. That was decided by the
      grep the drafts split taught us to run first, and the answer was not the one the
      drafts split gave. Nothing patches a module-level binding here; what
      `tests/test_fact_lifecycle.py:127,161,169,182` patches is `_complete_prepared` on
      the service *instance*, to simulate a crash inside `add_fact`. `add_fact` reaches
      it through `_run_fact_mutation`, so a delegation split would have moved that call
      onto an object the tests never touch and the four crash-recovery windows would
      have stopped being exercised. A base class keeps every internal call going through
      `self`, so the seam is where the tests already put it, and the engine is still
      constructible on its own - it needs only a repository and a Knowledge store - which
      is what makes it testable without the eight commands.

      22 methods before and after, no body or decorator changed, verified by AST
      comparison against the module loaded out of Git, and no method defined in two
      modules. The lifecycle/read split inside `service.py` was deliberately not done:
      it is a second subject boundary, not part of this one, and `service.py` stays
      above 500 lines until it is decided on its own.

      `application/services/operations.py` is done. It was listed at 518 lines and had
      reached 985, holding two subjects with different collaborators: the six Operation
      handlers (a new Operation type touches only these) and `OperationService` (an
      idempotency or submission change touches only this). It is now a package,
      `application/services/operations/` — `handlers.py`, `service.py`, `failures.py`
      for the failure-code table, `common.py` for the two source hashes both halves
      compare — re-exported from `__init__.py`, so `runtime/composition.py` and
      `api/services.py` are unchanged. No handler needed a mixin: they were already
      separate classes. No body changed, verified by AST comparison against the old
      module, and no test patches a module-level binding in it, verified by grep before
      the split — the failure mode the drafts split found.

- [ ] **TODO 19 — open question, not a task.** The port hierarchy was left unflattened
      during the `ports` split. `DraftRepository -> ReadinessRepository ->
      TrackingRepository -> ApplicationRepository` is linear and each level adds its own
      methods, so flattening means duplicating them. The MRO breakage that prompted the
      split came from base order inside one class, not from depth. Decide deliberately
      whether the chain earns its keep; do not refactor it as cleanup.
- [x] **TODO 15 — completed:** restored `UNIQUE` on `submissions.artifact_version_id`.
      The `0006` rebuild had dropped it, so the same artifact could be recorded as
      submitted twice in a table with no-update and no-delete triggers — a permanent
      claim that a CV was sent twice when it was sent once.

      **`NOT NULL` was deliberately not restored.** The item recorded the M1 column as
      `NOT NULL UNIQUE`, but that shape predates external submissions.
      `record_external_submission` passes `artifact_version_id=None` when the candidate
      applied through a company form, so `NOT NULL` would reject a supported case.
      SQLite permits repeated NULLs under `UNIQUE`, so nullable-and-unique gives both
      properties at once.

      The item said this needed its own migration. It no longer did: with the chain
      squashed to one baseline and no database anywhere, it is a one-token schema edit.
      The frozen fingerprint moved by exactly one entry, `TEXT` to `TEXT UNIQUE`, with
      the entry count unchanged at 80.
- [ ] **TODO 20:** decide whether the AI task contract belongs in `knowledge_context`.
      Stage G made `ai/contracts/task_contracts.json` the single source of contract and
      prompt versions, and both are stored on every provider run and on the registered
      response artifact. They are deliberately **not** in `Knowledge.versions()`, so
      editing a prompt does not stale existing drafts and does not move any
      `knowledge_context_hash`. That was the conservative choice for a boundary that was
      already Class B: adding them would move every stored hash and every golden that
      depends on one. Decide it on its own, with the hash movement stated up front.
- [x] **TODO 21 — completed:** `approve_draft` writes `language` into the
      DecisionRecord's `structured` payload, sourced from `draft.language` — the language
      of the exact document being approved, not of the latest analysis and not of the
      current projection. The export was already reading `structured["language"]`; it now
      finds a value there, so `- Language: en` / `- Language: he` renders beside the
      populated Track, Profile, Emphasis, and Fit instead of a blank.

      **No backfill, by design.** DecisionRecords are immutable, so records written before
      this change keep their blank Language and stay recoverable only by joining back to
      their bound analysis. The fix applies to new approvals only.

      Class B, and gated as one: the stored value's meaning changed, but no migration, no
      OpenAPI change, and no artifact-layout change — `structured_json` is an untyped
      payload column and the API never exposes it. The regression
      (`test_latest_decision_uses_revision_order_when_approvals_share_a_timestamp`)
      approves twice on
      one Application, in `en` then `he`, and re-reads the first record while both the
      latest analysis and the newest revision say `he`: that is what proves the export
      reads the stored record rather than recomputing from what is current.
- [x] **TODO 22 — completed:** `latest_decision` no longer treats the
      second-resolution `created_at` value as a total order. It joins the decision's
      immutable `ArtifactVersion` and orders first by that logical artifact's
      `version_number`, with deterministic tie-breakers that do not treat a UUID as a
      clock. A regression fixes two approvals to the same timestamp and proves both the
      repository query and HTTP read return the second revision's decision. No migration
      or schema change was required.
- [x] **TODO 23 — completed:** the golden hash comparison now runs in the default
      non-browser suite. The item said the file was marked `browser`; only one of its two
      tests was, and not by a marker. `BROWSER_FIXTURES` in `tests/conftest.py` marks any
      test that requests `render_validator`, and that one test mixed two subjects in one
      body: the golden hashes and HTML content assertions, then PDF geometry and the
      ATS/layout report.

      Split by subject, not by marker.
      `test_representative_profiles_match_their_golden_ready_outputs` keeps
      classification, Markdown, selection, the `markdown_body_sha256`/`html_sha256`
      comparison, and the HTML assertions — it drops the `render_validator` fixture, so
      collection stops marking it and the Class B gate is in the default run.
      `test_golden_outputs_pass_render_validation` is new and holds only what needs
      Chromium.

      The browser half re-asserts `case["snapshot"]["html_sha256"]` on the document it
      renders before validating it. Without that, the two halves could hash one document
      and validate another; with it, the report is evidence about the exact bytes the
      hash test pinned. Both build through `_build_case`, so the fixture setup cannot
      drift between them.

      No golden fixture, hash, or assertion changed — the assertions were partitioned,
      not rewritten. Test count moves by exactly +1: the default non-browser suite gains
      one test, the browser suite still collects one from this file.
      `test_persisted_plan_reproduces_the_computed_selection` was already in the default
      suite and is untouched.
- [ ] **TODO 24 — backend-suite reduction, first boundary complete.** Consolidated
      duplicated backend evidence across 17 test files without changing production code.
      The user-run non-browser gate moved from **451 passed, 4 deselected** to **300 passed,
      3 deselected**; the complete **-152 collected-item** delta and the retained safety
      boundaries are reconciled in `docs/m4-remaining.md` under “Current backend-test
      baseline”. The initial reduction is **151 non-browser tests (33.5%)**. Approximately
      75 further removals remain before the original half-size target is met; continue only
      through a fresh redundancy audit, with integrity, immutability, recovery, golden, and
      rendering failures cut last.
