# M1 Acceptance — Application Foundation

Status: **Passed on 2026-08-17**

Milestone: `docs/v2-implementation-plan.md` section 3 (M1 — Application foundation)

Baseline: `v1.0.0` / `2cc31c7`, 131 tests passing with `CV_REQUIRE_BROWSER=1`

Head at acceptance: `2666ed6`

## 1. Commits in this milestone

| Commit | Scope |
| --- | --- |
| `63a133d` | Workspace model, marker, roots, IDs, fail-closed guards, read-only v1 source adapter, configuration precedence |
| `1846578` | CandidateContext; candidate literals removed from drafting, rendering, filename, and link validation |
| `4e522ed` | Isolated development Workspace kept out of version control |
| `0f899fd` | domain / application / infrastructure separation |
| `2666ed6` | Application services behind ports, composition root, CLI on services, versioned export, architecture tests |

## 2. Checklist evidence

### Domain/application code imports no FastAPI, SQLite, path layout, or provider HTTP

`tests/test_architecture.py` enforces this on the import graph rather than by review:

- `test_layer_imports_no_infrastructure_technology[domain|application]` — no `sqlite3`,
  `fastapi`, `playwright`, `urllib`, `uvicorn`, `httpx`, or `requests` import in either layer.
- `test_layer_depends_only_inward[domain|application]` — domain imports only domain and shared
  primitives; application additionally may name the runtime Workspace value object, never an
  infrastructure adapter.
- `test_the_composition_root_is_the_only_application_link_to_infrastructure` — the façade's
  reference to the composition root stays inside a function body, so the application layer does
  not depend on every adapter at import time.
- `test_domain_modules_never_import_the_workspace` — domain receives paths, it does not resolve
  them.

`cv_engine/application/ports.py` defines the `ApplicationRepository`, `KnowledgeStore`,
`Renderer`, and `ClassificationProvider` protocols. `cv_engine/runtime/composition.py` is the
only module that binds them to `Repository`, `FileKnowledge`, `PlaywrightRenderer`, and
`OpenAIClassificationProvider`.

### The CLI completes the deterministic v1 Definition of Done through the services

Run against the isolated development Workspace (`purpose=development`, `data_class=copy`),
application `80068f71-6ae4-4cdc-8ba2-c9f5a0050bdb`:

```text
cv workspace init --purpose development --data-class copy --knowledge-from .
cv init
cv ingest    -> application + immutable job snapshot
cv analyze   -> sales / account-manager / account-growth, confidence 0.94, fit high
cv draft     -> working draft, pre-render validation passed
cv validate  -> passed
cv approve   -> v001 + decision record 887b1953-d8df-43b4-846e-8a0272abbe82
cv render    -> ready_validation.passed = true
cv ready     -> passed
cv reconcile -> passed, 5 artifact versions, fact lifecycle passed
```

`cv render` reported all eight groups green (`render`, `page_count`, `pdf`, `ats`, `links`,
`visual`, `direction`, `filename`), one page, ATS claim coverage 1.0, and produced
`Matan Malka - Account Manager - CV.pdf`. Every one of these commands is dispatched to an
application service; only the chained `cv fast` flow still goes through the façade.

### Selected facts, claims, validation outcomes, Ready eligibility, and decision behaviour retain semantic parity with v1

- The four golden fixtures (Development, Sales EN, Sales HE/RTL, Tech Sales) pass with their
  document body, selected fact IDs, sections, and rendered HTML hash unchanged from the v1.0.0
  baseline.
- The only difference in generated Markdown across all four cases was the `fact_store_version`
  line in the provenance header, which moved because a canonical fact was added. This was
  verified by generating each case with and without the new fact and diffing: every claim line,
  contact, section name, document name, and the HTML output were byte-identical.
- Golden fixtures now pin `markdown_body_sha256` and assert the header's knowledge version
  against the live fact store, so a content change still fails while a legitimate knowledge
  version bump is checked rather than frozen.

### Candidate name is not hardcoded in core or renderer policy

`tests/test_candidate.py::test_policy_modules_contain_no_candidate_literal` scans the ten policy
modules (`domain/drafts`, `domain/validation`, `domain/selection`, `domain/presentations`,
`domain/candidate`, `domain/profiles`, `domain/facts`, `application/workflow`,
`application/ready`, `infrastructure/rendering`) for `Matan Malka`, `מתן מלכה`, `matanmalka1`,
and `matan1391`. None remain.

Identity and contacts resolve from canonical facts through `CandidateContext`:
`common.identity.name` was added to `base/common.md` through the normal lifecycle
(`source_version` 1.0.0 -> 1.0.1, 86 -> 87 canonical facts). The generated v1 sources in
`infrastructure/canonical_data.py` were deliberately left alone, because their per-file hashes
are the recorded evidence in `docs/v1-retrospective-migration-verification.json`.

Remaining literals are in `infrastructure/canonical_data.py` (the frozen v1 migration baseline)
and `infrastructure/migration.py` (a historical artifact path). Both are v1 evidence, not policy.

### Normal v2 commands reject every missing, legacy, unknown, or unsafe marker; only the dedicated migration adapter can inventory an explicit v1 source read-only

`tests/test_workspace.py` covers:

- missing marker, unreadable marker, unknown workspace version, second marker;
- a legacy v1 root refused for both load and init, with no marker written into it;
- live data refused under a development or test purpose, both at creation and on load;
- declared roots confined to the Workspace, enforced at creation and against a hand-edited marker;
- `LegacyV1Source`: inventory leaves the source byte-identical, reads are bound to the inventory
  hash and fail when the source changes mid-run, traversal and absolute paths are refused, a
  marked Workspace is not accepted as a legacy source, and the SQLite connection is opened
  read-only (writes raise `sqlite3.OperationalError`);
- CLI: `workspace init`/`status`, refusal of a normal command against an unmarked root, and
  `workspace inventory-legacy` leaving the source unmarked.

The engine reaches its data only through `load_workspace`, so this decision is made in one place.

### All applicable v1 tests pass

```text
CV_REQUIRE_BROWSER=1 pytest tests -q  ->  185 passed
```

131 v1 tests at baseline, 185 now. No v1 coverage was removed; the added tests cover the
Workspace layer, the candidate context, and the architectural boundaries.

## 3. Defect found and fixed during the milestone

`tests/test_ready_integrity.py::test_failed_post_render_validation_does_not_set_ready` patched
`cv_engine.workflow`, a module path that resolved to the separately installed v1 package rather
than the worktree under test. The patch therefore had no effect and the test asserted nothing.
`tests/conftest.py` now refuses to run if `cv_engine` is imported from anywhere but the worktree,
and the test patches the renderer it actually exercises.

## 4. Deviations and open items

- `cv fast` is retained as the CLI compatibility flow and is documented in code as an explicit
  user approval instruction; it chains the same use-cases and cannot bypass validation or a
  blocker. It is the only remaining caller of the `Engine` façade.
- `Engine` still exists as a delegating façade for the v1 test suite. It holds no business logic
  and is removed once its callers address the services directly.
- The `UnitOfWork` boundary named in the plan is deferred to M2, where the v2 schema and
  multi-table commands that need it are introduced. M1 preserved v1's transaction behaviour
  unchanged.
- No v2 command opened v1 live data at any point. Development used
  `.workspace/dev` (`purpose=development`, `data_class=copy`) with its own knowledge copy.
