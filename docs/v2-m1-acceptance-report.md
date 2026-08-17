# v2.0 M1 Acceptance Report

Status: **CHANGES REQUIRED — M1 not accepted**

Date: 2026-08-17

Reviewed range: `bdbe20a..2666ed6`

Target contract: `docs/v2-implementation-plan.md` section 3.4

## 1. Outcome

M1 has substantial implemented progress: guarded Workspace/configuration, an isolated
development Workspace, CandidateContext, initial package separation, focused service
classes, ports, a manual composition root, CLI delegation, and expanded tests. The
committed implementation is not yet eligible for M1 acceptance because the current test
run is not isolated from the v1 worktree and the application dependency boundary does
not match the approved architecture.

No live v1 data write was observed. The import-isolation failure concerns Python code
loading, not access to the v1 live data Workspace.

## 2. Commit evidence

- `63a133d` — guarded Workspace, five roots, configuration precedence, separate IDs,
  and read-only legacy source adapter.
- `1846578` — CandidateContext and candidate-literal removal.
- `4e522ed` — local development Workspace ignored by Git.
- `0f899fd` — initial domain/application/infrastructure package split.
- `2666ed6` — six service classes, application ports, composition root, CLI delegation,
  versioned CSV export, and architecture tests.

The working tree was clean immediately after `2666ed6`.

## 3. M1 checklist

### 3.1 Domain/application imports no infrastructure technology or path layout

**FAIL**

- `cv_engine/application/services.py` imports the concrete runtime `Workspace`, stores
  its roots, constructs `working`/approved artifact paths, copies directories, and
  performs filesystem operations directly.
- `cv_engine/application/ready.py` imports `Workspace` and resolves filesystem paths.
- `cv_engine/application/workflow.py` imports runtime Workspace APIs and imports the
  composition root inside `Engine.__init__`.
- `tests/test_architecture.py` explicitly allows `application -> runtime`, although the
  approved dependency direction is
  `domain <- application <- infrastructure / api / cli / runtime`.

The application layer needs inward-facing value/port contracts. Workspace/path layout
and composition belong outside it. A temporary compatibility façade may remain, but it
must not weaken the application-layer import rule.

### 3.2 CLI completes the deterministic v1 Definition of Done through services

**PASS WITH EVIDENCE REPORTED, pending isolated rerun**

The CLI addresses Application, Analysis, Draft, Rendering, Tracking, and Knowledge
services directly; `Engine` remains only for the chained compatibility `fast` command.
The isolated development Workspace reportedly completed:

```text
ingest -> analyze -> draft -> validate -> approve -> render -> ready
```

All eight reported validation groups passed and the PDF was generated. This journey
must be repeated after the import-isolation failure in section 4 is fixed.

### 3.3 Semantic parity with v1

**UNVERIFIED**

The reported suite result is `185 passed` with `CV_REQUIRE_BROWSER=1`, and the golden
fixtures preserve body-level comparisons. However, the run cannot serve as acceptance
evidence while a missing v2 submodule is silently loaded from the v1 worktree.

### 3.4 Candidate name is not hardcoded in core or renderer policy

**PASS for literal removal; contract follow-up required**

Core/rendering code obtains candidate identity through CandidateContext and canonical
facts, and targeted tests scan policy modules for candidate literals.

Two source-of-truth details still require correction before M1 closes:

- `base/candidate.json` duplicates LinkedIn/GitHub URL values in `link_targets` instead
  of deriving contact details from canonical facts.
- `common.identity.name` is a new v2 fact with a semantic ID, while new v2 facts require
  UUID technical identity. Existing semantic IDs are preserved only when an existing
  fact ID actually exists to preserve.

### 3.5 Workspace guards and read-only legacy source

**PASS**

Normal Workspace loading is fail-closed for missing, legacy, unknown, and unsafe
markers. `LegacyV1Source` exposes read-only inventory-bound access and opens SQLite with
`mode=ro`. `.workspace/dev` exists as a marked development/copy Workspace with separate
state/artifact/temp/log roots. No live v1 data write was observed.

The `acknowledge_legacy_root` escape hatch in `create_workspace` should be removed or
made unreachable by construction because the approved migration is copy-based and the
dedicated read-only adapter is the only permitted legacy-source boundary.

### 3.6 All applicable v1 tests pass

**FAIL AS ACCEPTANCE EVIDENCE**

`cv_engine/runtime/workspace.py` imports `..models`, but
`cv_engine/models.py` no longer exists after the package split. In the current shared
environment, Python resolves that missing module to:

```text
/Users/matanmalka/Projects/resume_python/cv_engine/models.py
```

while the top-level package itself comes from the v2 worktree. The conftest guard checks
only `cv_engine.__file__`, so it does not detect this submodule-level cross-worktree
fallback. Until the import is corrected and tests assert that every loaded
`cv_engine.*` module belongs to the v2 tree, the `185 passed` result may include mixed
v1/v2 code and cannot close the acceptance item.

## 4. Additional application-contract blockers

The following do not require product decisions, but must be corrected before M1 is
accepted:

1. `AnalysisService.analyze` resolves `latest_snapshot` internally and
   `DraftService.draft` resolves `latest_analysis`. Approved v2 application commands
   require explicit immutable source IDs; legacy CLI convenience must resolve them
   before calling the service.
2. The current `ApplicationRepository` protocol is one broad port and exposes a
   concrete database `path`. Services call private concrete methods such as
   `_set_ready` and `_record_submission` that are absent from the protocol. Repository
   ports must expose intentional use-case operations and no private adapter API.
3. The architecture test currently encodes exceptions for the implementation instead
   of enforcing the approved inward dependency rule.

## 5. Required evidence for re-review

Before changing this report to `APPROVED`:

1. eliminate every cross-worktree module import and add a regression guard covering all
   loaded `cv_engine.*` modules;
2. enforce the approved import direction without allowing application to import
   runtime/infrastructure or know Workspace path layout;
3. move `latest` resolution to compatibility/query code and make application commands
   accept explicit source IDs;
4. replace private repository calls with declared focused ports;
5. restore CandidateContext/fact single-source and ID rules;
6. rerun the complete suite with `CV_REQUIRE_BROWSER=1` in the isolated v2 environment;
7. rerun the complete CLI deterministic journey in `.workspace/dev`;
8. record the exact commands, counts, hashes, and outcomes in this report.

M2 must not begin until these M1 acceptance blockers are closed.
