# Cleanup todos — performance and architecture findings

Non-milestone cleanup items, tracked here so they do not compete with M2 scope in
`docs/v2/m2-remaining.md`. Anything that becomes milestone work moves there.

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
- [ ] **TODO 14:** reassess architecture-test ceremony and replace manual checks with
      derived guards where possible without weakening the no-growth allowlist rule.
      Cheaper now than when it was written: three exception lists emptied on 2026-08-19
      (`ARCHITECTURE_DEBT_ALLOWLIST`, `PERSISTENCE_KNOWN_OFFENDERS`,
      `CANDIDATE_EVIDENCE_MODULES`), so the rules they qualified are now unconditional.

- [ ] **TODO 16:** split `cli.py` (1,200 lines). It holds the argparse tree (~200 lines),
      25 command handlers, output formatting, `export_csv`, and `fact_command`. Same
      shape as the `ports` split: a package whose `__init__` keeps the public surface, so
      no importer or command name changes. Verify by extracting exact source segments and
      diffing unparsed ASTs before and after, which is what caught a silently dropped
      decorator during the ports split.

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
