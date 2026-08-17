# M1 Acceptance — Application Foundation

Status: **Conditionally met — one clean full-suite run outstanding** (2026-08-17)

Milestone: `docs/v2-implementation-plan.md` section 3 (M1 — Application foundation)

Baseline: `v1.0.0` / `2cc31c7`, 131 tests passing with `CV_REQUIRE_BROWSER=1`

This file replaces both earlier records: the implementation report that declared M1
`Passed` and the review report (`docs/v2-m1-acceptance-report.md`) that declared it
`CHANGES REQUIRED`. The first was premature — it reported a suite result that the
review then showed was not isolated from the v1 worktree, so its test evidence could
not support the claim it made. Keeping two contradictory records would leave the
milestone's status a matter of which file a reader opened first.

## 1. Commits in this milestone

| Commit | Scope |
| --- | --- |
| `63a133d` | Workspace model, marker, roots, IDs, fail-closed guards, read-only v1 source adapter, configuration precedence |
| `1846578` | CandidateContext; candidate literals removed from drafting, rendering, filename, and link validation |
| `4e522ed` | Isolated development Workspace kept out of version control |
| `0f899fd` | domain / application / infrastructure separation |
| `2666ed6` | Application services behind ports, composition root, CLI on services, versioned export, architecture tests |
| this change | Review findings closed: cross-worktree import, artifact-location port, declared repository operations, fact ID and link source-of-truth |

## 2. Review findings and their resolution

The review raised eight findings. Seven are closed here; one is re-scoped with a stated
reason rather than silently dropped.

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
gained `test_application_composes_no_storage_paths`, which fails on `artifacts_root`,
`"working"`, or `mkdir(` appearing anywhere in the application layer.

### 2.3 Parity was unverified — closed

The finding was valid but overstated: the golden and parity path imports
`cv_engine.domain.models` throughout, and the fallback reached only `WorkspaceMarker`'s
base class. The parity conclusion stood on its merits. It has been re-established on a
clean run regardless — see section 3.

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
produces the same records — see section 4.

### 2.6 `latest` resolution inside commands — valid, re-scoped to M3

`AnalysisService.analyze` resolves `latest_snapshot` and `DraftService.draft` resolves
`latest_analysis`. The contract "commands use explicit source IDs; `latest` appears only
in read/query helpers" is an **M3** acceptance item (plan §5.4), not an M1 one
(plan §3.4). M1 required preserving v1 semantics, which is what these commands do. This
is recorded as the M3 gate rather than an M1 blocker; it is not closed here.

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

## 3. Checklist evidence

### Domain/application code imports no FastAPI, SQLite, path layout, or provider HTTP

`tests/test_architecture.py` enforces this on the import graph rather than by review:

- `test_layer_imports_no_infrastructure_technology[domain|application]` — no `sqlite3`,
  `fastapi`, `playwright`, `urllib`, `uvicorn`, `httpx`, or `requests` import in either
  layer.
- `test_layer_depends_only_inward[domain|application]` — domain imports only domain and
  shared primitives; application imports only domain, application, and `util`. It may no
  longer name the runtime at all.
- `test_no_application_module_reaches_the_composition_root` — the v1 compatibility façade
  lives outside the layered packages (`cv_engine/compat.py`) precisely so it can build
  services without dragging `runtime` or `infrastructure` into application code.
- `test_application_composes_no_storage_paths` — layout is asked for through
  `ArtifactStore`, never assembled in the application layer.
- `test_domain_modules_never_import_the_workspace` — domain receives paths, it does not
  resolve them.

`cv_engine/application/ports.py` defines `ApplicationRepository`, `ArtifactStore`,
`KnowledgeStore`, `Renderer`, and `ClassificationProvider`.
`cv_engine/runtime/composition.py` is the only module that binds them to `Repository`,
`FilesystemArtifactStore`, `FileKnowledge`, `PlaywrightRenderer`, and
`OpenAIClassificationProvider`.

### The CLI completes the deterministic v1 Definition of Done through the services

Re-run after the import fix, in a fresh isolated Workspace `.workspace/dev-rerun`
(`purpose=development`, `data_class=copy`, `workspace_id`
`36099957-a88a-400c-ad08-2a284333ef2e`), application
`a953e77f-be16-4875-8ad8-e7008f317a8f`. The earlier `.workspace/dev` run was left in
place rather than overwritten; a new Workspace was created because the knowledge copy in
the old one predates the fact ID and `link_target` changes.

```text
cv workspace init --purpose development --data-class copy --knowledge-from .
cv init
cv ingest    -> application a953e77f, job snapshot 451c210b
cv analyze   -> sales / account-manager / account-growth, confidence 0.94, fit high
cv draft     -> working draft, pre-render validation passed, 29 claims / 28 facts
cv validate  -> passed
cv approve   -> v001 + decision record 2d6fca6e-763e-47ca-99f3-7949db8ac4a1
cv render    -> ready_validation.passed = true
cv ready     -> passed
cv reconcile -> passed, 5 artifact versions, fact lifecycle passed, 87 canonical facts
```

`cv render` reported all eight groups green (`render`, `page_count`, `pdf`, `ats`,
`links`, `visual`, `direction`, `filename`), one page, ATS claim coverage 1.0, and
produced `Matan Malka - Account Manager - CV.pdf`
(`be52322d6cf88b67960563bbf46682ce794b0e1e1f2a3dd90a0a491215d8c2f8`). The rendered link
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

This is the one item still short of clean evidence, and the reason for the status at the
top of this file.

```text
CV_REQUIRE_BROWSER=1 python -m pytest -q  ->  187 passed, 1 failed in 145.48s
```

The failure was
`tests/test_facts_profiles.py::test_canonical_fact_store_has_unique_stable_ids`, which
still looked up the identity fact by its old semantic ID after 2.4 renamed it — a stale
test reference, not a defect in the code under test. It was corrected to resolve the ID
from `V2_IDENTITY_FACT` and assert it parses as a UUID, and that file was re-run:

```text
python -m pytest tests/test_facts_profiles.py -q  ->  4 passed
```

188 tests total; 131 at the v1 baseline. No v1 coverage was removed. The added tests
cover the Workspace layer, the candidate context, the architectural boundaries, the
cross-worktree module guard, and the fact `link_target` invariant.

**Outstanding:** one `CV_REQUIRE_BROWSER=1` run of the complete suite with the corrected
test in place, expected `188 passed`. Until that run exists, this item stands as 187/188
confirmed in one run plus one file confirmed separately. That is not the same thing as a
clean complete run and is not recorded as one.

## 4. Migration safety note for `link_target`

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

## 5. Deviations and open items

- **M3 gate, not an M1 blocker:** `latest` resolution inside `analyze` and `draft`
  (2.6). The M3 acceptance item stands; M1 preserved v1 semantics deliberately.
- `cv fast` is retained as the CLI compatibility flow and is documented in code as an
  explicit user approval instruction; it chains the same use-cases and cannot bypass
  validation or a blocker. It is the only remaining caller of the `Engine` façade.
- `Engine` still exists as a delegating façade for the v1 test suite, now at
  `cv_engine/compat.py`, outside the layered packages. It holds no business logic and is
  removed once its callers address the services directly.
- The `UnitOfWork` boundary named in the plan is deferred to M2, where the v2 schema and
  multi-table commands that need it are introduced. M1 preserved v1's transaction
  behaviour unchanged.
- No v2 command opened v1 live data at any point. Development used `.workspace/dev` and
  `.workspace/dev-rerun` (`purpose=development`, `data_class=copy`), each with its own
  knowledge copy.
