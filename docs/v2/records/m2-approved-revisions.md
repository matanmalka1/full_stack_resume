# M2 Boundary 2b-i — Approved revisions and artifact binding

Status: **Implemented and verified 2026-08-18.** Code/test commit: `3f030ad`.

Scope: the first two items of `docs/v2/m2-remaining.md` section B only:
ApprovedRevision ownership of immutable revision content, and artifact-version metadata bound
to that revision. Render-output relocation, Ready qualification, A2/A4/A5, submissions,
recruitment events, and the remaining section-B items stay out of scope.

Authority: `docs/v2/spec/product-spec.md` §6/§11/§16,
`docs/v2/spec/state-and-use-cases.md` §15–§16, `docs/v2/spec/architecture.md` §6.2/§7.1/§8,
and `docs/v2/spec/migration-plan.md` §6.7–§6.8.

## 1. Decisions

### D1 — `resume.json` is both revision content and the registered claim manifest

Architecture §6.2 says both that ApprovedRevision content contains immutable structured JSON
and a Markdown projection, and that the claim manifest is a separate registered artifact where
applicable. The current claim manifest is already the serialized `DraftDocument`; it is the
structured resume rather than a second document with an independent schema.

The implementation therefore writes one physical payload at
`revisions/{application_id}/{revision_id}/resume.json`. `approved_revisions` owns its path and
hash as structured content, while one `claim_manifest` artifact-version row registers that same
payload and binds it to the revision. `resume.md` is the other revision-owned payload and remains
registered as `resume_markdown`. No identical JSON bytes are copied to a second path merely to
give them another name.

### D2 — the revision is self-describing from already frozen records

`approved_revisions` freezes Application, JobSnapshot, JobAnalysis, SelectionPlan, WorkingDraft
ID/edit version/content hash, both revision payload paths and hashes, ValidationRun, and approval
decision provenance. CandidateContext and selection-policy fields are copied exactly from the
immutable SelectionPlan. Knowledge-context and validator versions are copied exactly from the
immutable ValidationRun. The facts version comes from the exact stored DraftDocument. Approval
does not recompute these values from current Knowledge.

Decision provenance in this boundary is the approval actor type, client, and command. The
referenced immutable analysis and plan own the classification, selection, accepted-gap, and
override decisions; the existing decision record remains the human/query compatibility record
and stays bound to the revision's Markdown artifact version.

### D3 — payloads precede one atomic SQLite approval commit

Approval seals the exact SQLite WorkingDraft, commits `resume.json` and `resume.md` through
`PayloadStore`, and re-hashes each final destination. Only then does one UnitOfWork insert the
ApprovedRevision, register its Markdown and claim-manifest artifact versions, write the decision
and audit event, deactivate the WorkingDraft, and perform the inherited Ready demotion when
applicable. A failed SQLite commit leaves only safe payload orphans for reconciliation; it cannot
expose a partial approval graph.

### D4 — revision sequence and artifact sequence are independent

`approved_revisions.version_number` is allocated as the next per-Application revision inside the
approval transaction. It is not calculated from artifact rows. Artifact versions retain their
existing per-logical-artifact sequence so `latest_artifact_version` and `artifact_versions`
continue to behave as before, with `revision_id` added as the new binding.

### D5 — no historical backfill and no render-output relocation

Migration `0005` adds nullable `artifact_versions.revision_id`. Existing rows remain `NULL`; no
revision identity is inferred for historical evidence. New approval artifacts and rendered
HTML/PDF/screenshot rows carry the exact revision ID.

Rendered bytes continue to use `ArtifactStore.render_targets` beside the approved source. Moving
them to `outputs/{application_id}/{revision_id}/` is carried forward separately because it also
changes renderer/browser and recruiter-filename path behavior.

## 2. Storage and lifecycle result

Migration `0005_approved_revisions.sql` creates the immutable table and its derived
`no_update_approved_revisions` / `no_delete_approved_revisions` trigger pair, adds the nullable
artifact foreign key, and indexes the binding. Approval now closes the WorkingDraft; a later
approval requires an explicit new WorkingDraft, as required by the approved lifecycle.

Ready integrity compares `revision_id` when present and retains directory-based compatibility
only for legacy rows whose binding is `NULL`. The public artifact and decision queries otherwise
retain their prior output, with `revision_id` exposed on artifact-version views.

## 3. Close-out evidence

Environment: macOS, repository interpreter `./.venv/bin/python`, branch `v2-main`.

| Gate | Result |
| --- | --- |
| Focused approval/persistence/database/migration/integration subset | **40 passed** |
| `./.venv/bin/python -m pytest -q -m "not browser"` | **160 passed, 4 deselected** — identical to the recorded baseline |
| `env CV_REQUIRE_BROWSER=1 ./.venv/bin/python -m pytest -q` | **164 passed** — no count drop |
| `tests/test_golden.py` | Passed; golden hashes did not move |
| `tests/test_architecture.py` | Passed; allowlist remains exactly `infrastructure/migration.py: imports subprocess` |
| Frozen M1 SQLite fingerprint | `tests/fixtures/m1_sqlite_master.tsv` byte-identical |
| Migration shape | A `0001`-only database upgrades through `0005` to the same `sqlite_master` shape as a fresh head database |
| Derived immutability guard | Passed without adding an exception; real ApprovedRevision update/delete attempts raise `immutable record` |
| Offline CLI | Fresh development/copy scratch Workspace with `OPENAI_API_KEY` unset completed ingest → analyze → draft → validate → approve → render → ready → reconcile |
| Revision payload proof | `resume.json` and `resume.md` existed at the §6.2 revision path before row registration and their SHA-256 values matched SQLite |
| Artifact binding proof | Claim manifest, Markdown, HTML, PDF, and screenshot rows all carried the exact ApprovedRevision ID |

The offline rehearsal produced one-page Ready output and reconciliation returned `passed=true`.
No command opened or modified any Workspace under `.workspace/`.
