# Task: put immutable artifact payloads behind an object-storage abstraction (S3/R2)

You are implementing this in the `resume_python` repository. Read this document fully
before touching anything. It is the authority for this task.

---

## 0. Authority, and a deliberate contradiction

**This prompt supersedes `CLAUDE.md` and `docs/v2/spec/` wherever they conflict, for this
task only.**

On 2026-08-25 the user decided to move this project toward a real deployment. `CLAUDE.md`
currently says the system is "local only, not deployed, no cloud" and lists cloud
deployment as a non-goal. **That is superseded. The contradiction is known and
intentional — do not stop to report it.** `CLAUDE.md` tells you to stop on a spec
conflict; this section is the answer to that conflict. Proceed.

Everything in this repository is development material. **There is no data to preserve**
and no backward compatibility to maintain.

### A second agent is working in parallel — do not touch its files

A Codex session is converting `cv_engine/infrastructure/persistence/` from raw SQL to
SQLAlchemy 2.0 Core + Alembic, in a **separate git worktree**
(`../resume_python-sqlalchemy`, branch `feat/sqlalchemy-postgres`).

**You must not edit anything under `cv_engine/infrastructure/persistence/`.** You work on
`main`, it works on its branch. The file sets are disjoint by design.

**The one place you could collide:** the `artifact_versions` table stores a payload
*reference* (a string) plus its hash. That other agent is converting how that row is
read and written. **You must not change what that string means or how it is formatted.**
Treat the stored reference as an opaque token whose format is frozen. If your design
seems to require a schema or format change, that is a stop condition (§7) — ask, do not
proceed.

### The frontend is also being worked on — expect it to change

Separately, work is starting on the React frontend in `frontend/`. **You will see files
under `frontend/` change, and commits touching it appear on `main`, while you work.**

That is expected and is not a conflict:

- **Never edit anything under `frontend/`.** It is not yours in this task.
- Do not treat a frontend change as something that broke your work, and do not try to
  reconcile it. Your task touches Python only.
- Do not run the frontend test suite (`npm test` / `vitest`). Its pass count is not your
  evidence, and a red frontend run tells you nothing about payload storage.
- If you `git pull` or rebase and see frontend commits, carry on. Only a change under
  `cv_engine/` is capable of affecting you.

If a frontend change genuinely appears to break something you own — for example an API
response shape you rely on — that is a stop condition (§7). Say so; do not fix it
yourself.

---

## 1. Documentation: what to read, what to ignore

This repository has ~3,300 lines of binding-sounding documentation, much of it describing
a local-only, SQLite-backed system.

| Status | Files | What to do |
| --- | --- | --- |
| **Binding** | `cv_engine/application/ports/` (this is *code*) | The contract. Satisfy it exactly. |
| **Context only** | `CLAUDE.md`, `docs/v2/spec/architecture.md` | Read for intent. Not a constraint on this task. |
| **Ignore entirely** | `docs/v2/records/*.md`, `m2-remaining.md`, `m3-remaining.md`, `m4-remaining.md` | Frozen evidence for closed boundaries. They describe the past. |

Two absolute rules:

1. **Code beats documentation on what *is*.** Where they disagree about current
   behaviour, read the code.
2. **This prompt beats documentation on what *should be*.**

**Do not edit anything under `docs/` except where S4 names it.**

---

## 2. The problem, stated precisely

Immutable payloads — job snapshots, approved revisions, rendered HTML/PDF/PNG, provider
responses, manifests — are written to the local filesystem by
`cv_engine/infrastructure/payloads.py` (`PayloadStore`, 525 lines).

**The good news: the application-layer contract is already storage-neutral.** This was
done deliberately and you must not undo it:

- `SnapshotPayload` (`ports/values.py:35`) carries `reference: str`, **not** a `Path`.
- `ArtifactStream` (`ports/values.py:62`) is documented as *"Deliberately carries no
  `Path`"* — architecture §14 forbids a filesystem location reaching an HTTP response.
- `SnapshotPayloadStore` / `RevisionPayloadStore` (`ports/outbound.py:76`) speak in
  references and bytes.

**So this task does not design a new contract. It replaces an implementation behind a
contract that is already correct.**

What is filesystem-bound is the *implementation*: `os.rename`, `mkdir`, `sha256_file`,
`Path.exists`, `resolve_within`.

### Scope boundary — what stays local, and why

Three things stay on the local filesystem. These are decisions, not oversights.

1. **`working/` drafts — the *mutable* draft only.** `FilesystemArtifactStore`
   (`infrastructure/artifacts.py`) owns the working draft. The user decided on 2026-08-25
   that this stays local: it is rewritten on every autosave, latency matters, and it is
   not an immutable record.

   **Do not touch** `working_paths()`, `write_working_draft()`, `load_working_draft()`,
   `working_markdown()`, or the `working/` layout. The `Path` references those carry are
   correct for what they do.

   **This fence is about draft storage, not about the whole class.** `ArtifactStore` also
   exposes `relative()`, which is *reference derivation*, not draft storage — and
   `rendering.py` uses it for rendered outputs, which are immutable payloads that belong
   in the object store. Changing that caller is in scope. See §3.

2. **`RenderTargets`.** Chromium (via Playwright) writes real files to real paths. It
   cannot write to an object store. `RenderTargets.html/pdf/screenshot` stay `Path`.

3. **Knowledge sources** (`base/`, `profiles/`, `rendering/`, `config/`). These are
   version-controlled inputs, not artifacts.

---

## 3. The seam

There are **two** write paths, not one. An earlier version of this prompt claimed a single
seam; that was wrong, and it was found during S1 on 2026-08-25.

**Path 1 — `PayloadStore.commit()` (`payloads.py:241`).** Five of the six payload
families go through it: `commit_snapshot`, `commit_draft_snapshot`,
`commit_provider_response`, and `commit_revision` (which commits two).

**Path 2 — the renderer, which bypasses `commit()` entirely.** Chromium writes
`targets.html/pdf/screenshot` to their **final** paths, and
`application/services/rendering.py:230-234` registers them with
`self.artifacts.relative(path)` + `sha256_file(path)`. That path never sees
`_approved_destination()` and never gets the overwrite refusal.

So rendered outputs need their own treatment: **render to a temporary directory, then
ingest the file into the store.** `RenderTargets` still carries `Path` — Chromium needs
a real file — but the path becomes temporary, and the store owns the final location.

Two hard conditions on that work:

- **The stored `reference` string must come out byte-identical to what `relative()`
  produces today.** Another agent is converting the `artifact_versions` table right now
  (§0). If you cannot reproduce the exact format, stop and ask.
- **The `sha256` must be computed over what goes into storage**, not over a file re-read
  afterwards — the same principle as `open_artifact()` (§4).

**Do these separately.** Convert the five `commit()` families first, in their own commit.
Rendered outputs are a second, separate commit, because that one alone touches
`rendering.py`. Do not mix them.

`commit()` today does: derive target → `mkdir` → refuse if exists → write to a temp file
under `temp_root` → validate → hash → `os.rename` into place.

The `*_path()` methods (`snapshot_path`, `revision_path`, `draft_snapshot_path`,
`output_path`, `provider_path`, `manifest_path`) are **pure key derivation** — they build
a location from validated components. They translate almost directly into object keys.

### Direct PUT — no temp key, no copy

Write straight to the final key.

The temp-then-rename pattern exists because a local filesystem can expose a partially
written file. **S3 has no such window:** a `PutObject` is atomic at the object level, and
since December 2020 S3 provides strong read-after-write consistency, including for LIST.
R2 is likewise strongly consistent. Reproducing temp+copy would be porting a workaround
for a problem that does not exist, and `CopyObject` is not atomic anyway.

Preserve the **refusal on overwrite** — immutable payloads must never be silently
replaced. Use a conditional write (`IfNoneMatch: "*"`, supported by S3 and R2) and map a
precondition failure onto the same error the local store raises today.

---

## 4. What to build

```
ObjectStore (Protocol)     — keys and bytes. No Path. No directories.
├─ LocalObjectStore        — filesystem. The default. Behaviour-identical to today.
└─ S3ObjectStore           — boto3. R2 via endpoint_url.

PayloadStore(object_store) — same public contract, storage injected.
```

`runtime/composition.py:108` already reads `payloads or PayloadStore(workspace)`, so the
injection point exists. Configuration follows the existing `Setting(...)` pattern in
`runtime/config.py` — do not invent a second configuration mechanism.

Use **`boto3`**. R2 is S3-compatible and boto3 has the best support. Add it as an
**optional** dependency so the local path needs no cloud SDK.

### Non-negotiable behaviours to carry across

These exist because something went wrong once. Preserve every one:

- **Containment.** `_component()`, `_approved_destination()`, `resolve_within()` reject
  path traversal and non-approved layouts. In an object store this becomes **key
  validation** — the same refusals, expressed for keys. Do not drop it because "S3 has no
  `..`". A crafted key must still be refused.
- **`open_artifact()` ordering** (`payloads.py:353`). Read its docstring in full before
  touching it. The hash must cover **the bytes returned**, captured once — not a location
  that is verified and then reopened. That closes a time-of-check/time-of-use window.
  This property must survive the move.
- **The error taxonomy.** `ArtifactContainmentRefused`, `ArtifactPayloadMissing`,
  `ArtifactHashMismatch`, `InfrastructureFailure` must still be raised from the same
  conditions. A network failure is `InfrastructureFailure`; a missing key is
  `ArtifactPayloadMissing`. Do not let a `botocore` exception escape.
- **No `Path` leaves the store outward.** Only `RenderTargets` carries one, and only
  inward to the renderer.

---

## 5. Stages and gates

**You do not run the test suite. The user runs it.** (`CLAUDE.md`: "Do not run tests.")
At the end of each stage, stop and hand back ordered commands, what each proves, and the
expected numbers.

You may freely run: `python -c "import ..."`, `ruff`, `pyright`/`mypy`, `grep`, and
one-off scripts that exercise a single method you are actively debugging. Do not run
`pytest`, `vitest`, or anything that starts Chromium.

### S1 — `ObjectStore` + `LocalObjectStore`

Define the protocol and the local implementation. Do **not** wire it in yet.

The local implementation must reproduce today's behaviour exactly, including the
overwrite refusal and containment checks.

**Hand back:** the new files and a `ruff` / type-check result. Say plainly that no
behaviour has changed yet because nothing consumes it.

### S2a — `PayloadStore` consumes `ObjectStore`

Rewrite `PayloadStore` internals to go through the injected store. Delete the temp-file
machinery (§6). Public methods keep their exact signatures and return types.

This covers the five families that already go through `commit()`. **Leave rendered
outputs alone in this stage.**

**This is a pure refactor: with `LocalObjectStore` injected, behaviour is identical.**

### S2b — Rendered outputs (separate commit)

Route the three rendered outputs through the store: render to a temporary directory, then
ingest. This is the only stage that touches `application/services/rendering.py`, which is
why it is kept apart from S2a.

Honour both conditions in §3 — the `reference` format is frozen, and the hash covers what
is stored.

**Gate for S2a + S2b — hand back:**
- `./.venv/bin/python -m pytest -m "not browser"` — expected: unchanged from baseline
  (331 test functions today). Any difference is a finding, not noise.
- `docs/v2/smoke-run.md` end to end — must still reach `preparation_state: ready`. This is
  the only check that exercises the render path, so it is not optional here.

### S3 — `S3ObjectStore`

Add the boto3 implementation, the optional dependency, and configuration. Local stays
the default; nothing changes for a user who configures nothing.

**Gate — hand back:** the same two commands, plus how to point the store at MinIO or R2
and run the smoke run against it.

### S4 — Documentation

Only now edit `docs/`. Update `CLAUDE.md` and `docs/v2/spec/architecture.md` to describe
object-storage-backed immutable payloads and the local default. Note which local-only
statement stopped being true.

Do **not** edit `docs/v2/records/` or the frozen `m2/m3/m4-remaining.md` trackers.

---

## 6. Delete what the change makes dead

**This is a replacement, not an addition.** When the object store takes over a
responsibility, the filesystem code that held it is deleted in the same stage — not
deprecated, not kept behind a flag, not left with a comment saying it is unused.

Expected deletions:

- The temp-staging path in `commit()`: `_TEMP_DIRECTORY`, the `.tmp` write, the
  `os.rename` publish.
- **`temp_orphans()` and `TempOrphan`.** Verified on 2026-08-25: `temp_orphans` has **no
  caller anywhere in the codebase**. It is already dead code today, and direct PUT
  removes its subject entirely. Delete both, and say so explicitly in your report rather
  than folding it into the refactor.
- Any helper, import, or constant left with no caller afterwards.

**Forbidden:** compatibility shims, aliases to old names, `if backend == "local"`
branches scattered through `PayloadStore` (the polymorphism belongs in `ObjectStore`),
and commented-out old code kept "for reference" — Git has it.

Before deleting, grep the symbol across `cv_engine/` **and** `tests/`. If the only
remaining caller is a test that exists solely to test the deleted mechanism, the test
goes too — say so and state what coverage was lost.

If deleting something would change observable behaviour, that is a §7 stop condition.

---

## 7. Stop and ask — do not guess

Stopping is the expected behaviour, not a failure. Stop when:

- your design appears to require changing the stored reference format, or anything about
  the `artifact_versions` schema (**that belongs to the other agent — §0**);
- preserving behaviour would require changing a signature in `ports/`;
- you cannot tell whether a containment check is still meaningful in key form;
- a test asserts on something the change would alter;
- the local and S3 implementations cannot be made to behave identically for some case;
- any acceptance criterion cannot be honestly ticked.

State the problem and its consequences, then wait.

---

## 8. Acceptance

1. `ports/outbound.py` and `ports/values.py` are **unchanged**.
2. `grep -rn "sqlalchemy\|boto3\|botocore" cv_engine/application/ cv_engine/domain/ cv_engine/api/`
   returns **0** — storage stays sealed in infrastructure.
3. `PayloadStore`'s public methods keep their exact signatures and return types.
4. With `LocalObjectStore`, the backend suite matches the 331-function baseline, with
   every difference explained.
5. `docs/v2/smoke-run.md` reaches `preparation_state: ready` with the local store.
6. The same smoke run reaches `ready` against MinIO or R2.
7. Overwriting an existing immutable payload is refused in **both** implementations.
7b. **All six payload families go through the store** — including the three rendered
   outputs. `rendering.py` no longer registers a payload it wrote directly to a final
   path, and the `reference` strings it stores are byte-identical to the previous format.
8. `open_artifact()` still hashes the bytes it returns, captured once.
9. Temp-staging and `temp_orphans()` are deleted, not disabled.
10. `cv_engine/infrastructure/persistence/` is **untouched**.
11. `frontend/` is **untouched** — no file under it appears in any of your diffs.

---

## 9. Reporting

Per `CLAUDE.md`: **never claim completion with "implemented" alone.** Report what passed,
what failed, and what remains. A hard failure is never relabelled a warning.

For each stage, hand back:

- the commits and their diffs — small and intentional, no unrelated changes mixed in;
- the ordered commands, each using `./.venv/bin/python`, with what each proves;
- the predicted test count and an explanation for every deviation;
- **what you deleted** (§6), confirming nothing was left as a shim or dead-but-present;
- anything you could not verify because you did not run it — state it plainly.
