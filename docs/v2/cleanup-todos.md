# Cleanup todos — performance and architecture findings

Non-milestone cleanup items, tracked here so they do not compete with milestone scope in
the current tracker, `docs/v2/m3-remaining.md`. Anything that becomes milestone work moves
there.

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
- [ ] **TODO 11:** slim `ServiceBase` by moving single-consumer helpers to their owning
      services.
- [x] **TODO 12:** enforce the existing ports with a type checker or propose a
      specification-compliant reduced port surface.
- [x] **TODO 13:** measured 178/201 MB dedicated virtualenvs and one shared 554 MB
      Playwright browser cache; with a warm `uv` cache, a 173 MB logical environment added
      about 2 MB physically while keeping independent editable environments and Workspace state.
- [x] **TODO 14 — completed (`8429aa5`).** Every rule in `tests/test_architecture.py` was
      classified by what it actually proves. Two were hand-maintained and are now derived;
      the rest already read their answer out of the code and were left alone. Nothing was
      removed: no rule turned out to guard something that had gone away.

      The one that mattered was latent. The rule forbidding `domain`/`application` from
      naming a Workspace root checked `artifacts_root`, `knowledge_root`, and `base_dir` —
      while `runtime/workspace.py` defines five roots. `state_root`, `temp_root`, and
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
      | `runtime/operations.py` | role — `backup`, `composition`, `config`, `workspace` | **wrong**; renamed to `execution.py` |

      Renaming all four would have broken four internal conventions to fix one
      cross-package collision that no importer or traceback is actually ambiguous
      about: a relative `from .operations import` can only mean the sibling, and a
      traceback prints the full path. Only `runtime/` was named for what the module is
      about while its siblings are named for what they do. It holds
      `ForegroundOperationExecutor` and `OperationWorker` — the two hosts an Operation
      runs inside — so `execution.py` says what the others say.

      Two importers changed: `runtime/composition.py` and `tests/test_operations.py`.

- [ ] **TODO 18:** the remaining files over 500 lines, in descending order:
      `application/services/knowledge.py` (723, grew in §4.5), `domain/models.py` (676),
      `application/services/drafts.py` (646), `infrastructure/persistence/operations.py`
      (639), `application/state.py` (528), `domain/drafts.py` (524),
      `application/services/operations.py` (518). Take them one at a time and only where
      a file holds more than one subject; size alone is not a defect.

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
      (`test_decision_record_states_the_approved_draft_s_own_language`) approves twice on
      one Application, in `en` then `he`, and re-reads the first record while both the
      latest analysis and the newest revision say `he`: that is what proves the export
      reads the stored record rather than recomputing from what is current.
