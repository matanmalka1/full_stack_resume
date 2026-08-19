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
