# Performance and architecture findings

Execution rule: work serially. Complete and verify one item, then wait for explicit user
approval before starting the next. These items do not silently expand product semantics
or weaken an existing acceptance gate.

- [x] **TODO 1 — completed (`ab63ef6`):** added Ruff, defined the lint/format contract,
      removed dead/copied imports, and verified no behavioral change.
- [x] **TODO 2:** split the default fast non-browser pytest run from an explicit
      browser-complete gate.
- [ ] **TODO 3:** evaluate pytest-xdist isolation and add it only after explicit
      dependency-baseline approval.
- [ ] **TODO 4:** convert redundant CLI subprocess tests to in-process `cli.main(...)`
      calls while retaining one or two real process-boundary tests.
- [ ] **TODO 5:** split `cli.main()` into a command-handler registry without changing
      CLI signatures, output, or errors.
- [ ] **TODO 6:** extract `validate_draft` into an ordered registry of focused validation
      rules without changing validation behavior.
- [ ] **TODO 7:** remove the transitional composite repository while preserving the
      approved repository boundaries and UnitOfWork behavior.
- [ ] **TODO 8:** retire `persistence/primitives.py` without duplicating UUID policy.
- [ ] **TODO 9:** retire `persistence/serialization.py` while preserving the
      serialization-version contract.
- [ ] **TODO 10:** retire `compat.py` by moving explicit-source compatibility resolution
      to the CLI boundary.
- [ ] **TODO 11:** slim `ServiceBase` by moving single-consumer helpers to their owning
      services.
- [ ] **TODO 12:** enforce the existing ports with a type checker or propose a
      specification-compliant reduced port surface.
- [ ] **TODO 13:** measure and reduce per-worktree virtualenv/Chromium duplication without
      sharing mutable Workspace state.
- [ ] **TODO 14:** reassess architecture-test ceremony and replace manual checks with
      derived guards where possible without weakening the no-growth allowlist rule.
