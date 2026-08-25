# Task: replace raw-SQL SQLite persistence with SQLAlchemy 2.0 Core + Alembic on PostgreSQL

You are implementing this in the `resume_python` repository. Read this document fully
before touching anything. It is the authority for this task.

---

## 0. Authority, and a deliberate contradiction

**This prompt supersedes `CLAUDE.md` and `docs/v2/spec/` wherever they conflict, for this
task only.**

On 2026-08-25 the user decided:

- PostgreSQL replaces SQLite. **SQLite is dropped entirely** — not kept as a second
  dialect.
- SQLAlchemy 2.0 **Core** (`MetaData` / `Table` / `select()`) replaces hand-written SQL.
- **Alembic** replaces the in-repo migration runner.
- **Pydantic stays** exactly as it is.
- `cv workspace backup` / `restore` are **removed**, not ported.

This contradicts:

| Document | What it says | Status |
| --- | --- | --- |
| `CLAUDE.md` | "PostgreSQL ... are not [authorized]" | Superseded. Updated in S5. |
| `CLAUDE.md` | CLI must reach Ready offline | Superseded — now needs a running Postgres. |
| `CLAUDE.md` L116-118, L184 | `cv workspace backup` as a safety control | Superseded — command is removed. |
| `docs/v2/spec/architecture.md` §6.1 | "SQLite stores structured state" | Superseded. Updated in S5. |

**The contradiction is known and intentional. Do not stop to report it.** `CLAUDE.md`
tells you to stop on a spec conflict; this section is the answer to that conflict.
Proceed.

There is no data to preserve. Every environment is development-only. **No data migration
is in scope** — the Alembic baseline creates a fresh, empty database.

---

## 1. Documentation: what to read, what to ignore

This repository has 3,337 lines of binding-sounding documentation, and **17 files mention
SQLite**. Most of it is about to be wrong. Handle it as follows.

| Status | Files | What to do |
| --- | --- | --- |
| **Binding** | `cv_engine/application/ports/` (this is *code*) | The contract. Satisfy it exactly. |
| **Binding** | `docs/v2/process/execution-protocol.md` | Process rules. Still apply. |
| **Context only** | `CLAUDE.md`, `docs/v2/spec/architecture.md` | Read for intent. **Not** a constraint on this task. Updated in S5. |
| **Ignore entirely** | `docs/v2/records/*.md`, `docs/v2/m2-remaining.md`, `m3-remaining.md`, `m4-remaining.md` | Frozen historical evidence for closed boundaries. They describe the past, not the target. |

Two absolute rules:

1. **Code beats documentation on what *is*.** Where a doc and the code disagree about
   current behaviour, read the code.
2. **This prompt beats documentation on what *should be*.**

**Do not edit anything under `docs/` before S5.** If you notice a doc that is now wrong,
do not fix it — S5 owns that. Record it in your S5 notes instead.

---

## 2. The contract you must not break

`cv_engine/application/ports/` (1,201 lines of `Protocol` definitions) **is the
specification**. It does not change.

Verified before this task started:

```
grep -rn "sqlite" cv_engine/application/ cv_engine/domain/ cv_engine/api/   →  0 matches
```

**This must still return 0 when you are done, and no SQLAlchemy symbol may appear there
either.** Persistence stays sealed inside `cv_engine/infrastructure/persistence/`.

Concretely:

- Every method signature in `ports/` keeps its **exact** name, parameters, and return
  type. 27 of them return `dict[str, Any]`; 10 return typed models. **Do not "improve"
  either group into ORM entities.**
- Do not add, remove, or reorder a port method.
- `application/`, `domain/`, and `api/` are **not** edited in S1–S4.

### Core, not ORM — and why

This was decided deliberately. Do not revisit it.

**Use:** `MetaData`, `Table`, `Column`, `select()`, `insert()`, `update()`, `delete()`,
`Connection`, explicit `join()`.

**Do not use:** `DeclarativeBase`, `Session`, `relationship()`, lazy loading, identity
map, cascades, `backref`.

Reasons, so you do not re-litigate them mid-task:

1. The ports return `dict`, not entities. An ORM would load a managed object only to
   flatten it back to a `dict` in 27 places — pure overhead.
2. `SqliteRepositoryBase.read_transaction()` binds one projection to one stable snapshot.
   Lazy loading directly contradicts that guarantee.
3. 14 of 22 tables are immutable. There is nothing for dirty-tracking to track.

---

## 3. Scope, measured

```
  3,151 lines   cv_engine/infrastructure/persistence/     ← rewritten
     22 tables
     38 triggers  (32 are one identical pattern)
     14 immutable tables of 22
      9 test files touch sqlite3 directly                 ← will break; that is expected
    331 backend test functions                            ← baseline
```

**Baseline proven on 2026-08-25, before this task.** Reproduce it at the end:

- `docs/v2/smoke-run.md` runs `ingest → analyze → draft → validate → approve → render →
  ready` and reaches `preparation_state: ready`, offline, with `OPENAI_API_KEY` unset.
- Frontend: 156/156 tests passing.

---

## 4. Working environment — worktree, and a fresh Postgres

Work in a **separate git worktree** so the user's `main` stays clean:

```bash
git worktree add ../resume_python-sqlalchemy -b feat/sqlalchemy-postgres
cd ../resume_python-sqlalchemy
python3 -m venv .venv
./.venv/bin/python -m pip install -e '.[test]'
./.venv/bin/playwright install chromium
```

`execution-protocol.md` §9.4 requires each worktree's own `./.venv/bin/python`. Evidence
produced under another worktree's environment is not accepted. **Every command you hand
back must use `./.venv/bin/python` explicitly.**

Postgres is a **fresh local instance you create** — the user has none. Write
`docker-compose.yml` in S2:

- image `postgres:17`
- a named volume
- a non-default port (e.g. `5433`) so it cannot collide with an existing install
- credentials via env vars, defaulted for local dev

Connection settings follow the existing `runtime/config.py` `Setting(...)` pattern
(`CV_DATABASE_URL` or equivalent). Do not invent a second configuration mechanism.

---

## 5. Stages, sub-agents, and gates

**You do not run tests. See §5.1 — read it before you start.** At the end of each stage,
stop and hand back ordered commands, what each proves, and the expected numbers.

```
S1  foundations           serial, you alone
S2  Alembic + schema      serial, you alone
    ══════ GATE — user runs ══════
S3  11 repositories       TWO SUB-AGENTS IN PARALLEL
    ══════ GATE — user runs ══════
S4  runtime cleanup       serial, you alone
S5  documentation         serial, you alone
```

### 5.1 Do not run the test suite

**You never invoke `pytest`, `vitest`, `playwright`, or any suite runner. The user runs
them.** This is not a formality — it is the single biggest waste of time available to you
on this task, and it is a hard rule from `CLAUDE.md`: *"Do not run tests. The user runs
them."*

Why it matters here specifically:

- The backend suite is 331 test functions. Running it after each of ~40 converted methods
  costs hours and tells you almost nothing you did not already know.
- Until S2 lands, **the suite cannot pass at all** — the schema does not exist yet. A red
  run during S1 is not information.
- Until S3 finishes, **it cannot pass either** — half the repositories are converted. Both
  lanes will see failures caused by the *other* lane's unconverted files. Those are not
  defects, and chasing them is pure waste.
- Anything involving `render` starts a real Chromium. Never trigger that to "check
  something".

So: **do not run the suite to find out whether you are on track.** Convert, reason, move
on. The gate at the end of the stage is what establishes truth.

**What you may run instead** — cheap, targeted, and non-interactive:

| Allowed | Use it for |
| --- | --- |
| `./.venv/bin/python -c "import cv_engine..."` | Does it import? Is the `MetaData` well-formed? |
| `./.venv/bin/python -m mypy` / `pyright` | Types, without executing anything |
| `./.venv/bin/ruff check` | Lint |
| `grep` / `rg` | Structural checks: leaked symbols, missed call sites |
| `alembic upgrade head` on a scratch DB | S2 only — schema builds |
| A one-off script hitting **one** repository method | Diagnosing **one** specific uncertainty |

That last row is the only sanctioned way to execute persistence code, and it is for
answering a question you have already framed — not for sweeping.

**If you believe you must run the suite, that is a §7 stop condition.** Say why, and wait.

### Why S1 and S2 are not parallel

`execution-protocol.md` §7 rules out parallel lanes when packages are sequentially
dependent or converge on a shared file. S1 and S2 are both: every repository inherits from
the S1 base and writes against the S2 `MetaData`. Two agents there would collide on the
same files and cost more than they save. **Do not parallelise S1 or S2.**

S3 is ~2,630 of the 3,151 lines and *does* partition cleanly. That is where parallelism
pays.

---

### S1 — Foundations (serial)

Add `sqlalchemy>=2.0,<3`, `alembic>=1.13,<2`, `psycopg[binary]>=3.2,<4` to
`pyproject.toml`. Remove nothing else from the dependency list.

Replace, keeping the existing shapes:

- `connection.py` → a SQLAlchemy `Engine` factory. This stays the single
  connection-policy authority, exactly as the current docstring describes.
- `SqliteUnitOfWork` → `SqlAlchemyUnitOfWork`, satisfying the `UnitOfWork` protocol
  (`ports/repositories.py:34`). Preserve the current semantics: **a successful scope
  still rolls back unless `commit()` is called explicitly.**
- `SqliteRepositoryBase` → `SqlAlchemyRepositoryBase`, keeping `bind()`, `transaction()`,
  `read_connection()`, and `read_transaction()`. `read_transaction()` must still bind one
  projection to one consistent snapshot — use a single `Connection` inside one
  transaction with `REPEATABLE READ`.
- Create the `MetaData` module holding all 22 `Table` definitions. Types map explicitly:
  SQLite `TEXT` ids → `String`/`UUID`, `*_json` columns → `JSONB`, timestamps → the type
  the current code actually stores. **Do not silently change a stored value's meaning** —
  if a column's intended type is ambiguous, stop and ask (see §7).

Write **no repository logic** in S1.

**Hand back:** the dependency diff and the `MetaData`. Do not hand back a suite command
here — the schema does not exist until S2, so nothing meaningful can pass yet. State that
plainly rather than offering a command that will fail.

---

### S2 — Alembic and schema (serial)

- Initialise Alembic against the S1 `MetaData`; `autogenerate` must work.
- **One baseline migration** creating all 22 tables. Delete
  `infrastructure/persistence/migrations/*.sql` and the `schema.py` runner they served —
  Alembic replaces both.
- Write `docker-compose.yml` (§4).

**The 38 triggers — build this as a derived guard, not a hand-written list.**

`CLAUDE.md` is explicit: *"Prefer deriving a check from the code or schema over
maintaining a list by hand... make it a small list of deliberate exceptions, so forgetting
to register something fails instead of passing."*

So:

- **One** PL/pgSQL function raising on UPDATE/DELETE (the Postgres equivalent of
  `RAISE(ABORT, 'immutable record')`).
- Attach it by **iterating a table list**, defaulting to *immutable unless explicitly
  exempt*. Inverting this default is what previously caught a table unguarded since M1.
- The 14 immutable tables today: `application_events`, `approved_revisions`,
  `artifact_versions`, `artifacts`, `audit_records`, `decision_records`, `fact_events`,
  `generation_runs`, `job_analyses`, `job_snapshots`, `recruitment_events`,
  `selection_plans`, `submissions`, `validation_runs`.
- The remaining 8 are the **exception set** — list them explicitly, so a new table is
  immutable by default.
- The 3 status-CHECK triggers become Postgres `CHECK` constraints.

**Hand back:** `alembic upgrade head` against a fresh container, plus a way for the user
to see all 22 tables and every trigger attached.

---

### S3 — Repositories (TWO SUB-AGENTS, PARALLEL)

Spawn **two** sub-agents with **exclusive, disjoint file ownership**. Neither may touch
the other's files, and neither may edit S1/S2 output.

| Lane A (~1,260 lines) | Lane B (~1,370 lines) |
| --- | --- |
| `operations.py` (641) | `preparation.py` (515) |
| `artifacts.py` (399) | `drafts.py` (458) |
| `audit.py` (129) | `tracking.py` (175) |
| `applications.py` (91) | `knowledge.py` (132) |
| | `settings.py` (90) |

Give each lane this prompt's §2 (the contract), **§5.1 (do not run tests)**, §6
(translation rules), **§6.1 (delete dead code)**, and §7 (stop conditions). Each lane converts its files from raw SQL
to SQLAlchemy Core, method by method, preserving behaviour exactly.

**Tell each lane explicitly that it must not run any test suite.** A lane cannot get a
meaningful result anyway: the other lane's files are still unconverted, so every failure
it sees is ambiguous. Two agents each running 331 tests on a half-converted tree is the
worst-case waste on this task. Lanes convert and report; the gate after S3 is the first
honest measurement.

You are the lead: you integrate, you resolve every judgment call, and **you never delegate
a decision to a lane** (`execution-protocol.md` §1).

**Hand back:** `./.venv/bin/python -m pytest -m "not browser"`, with the expected count
stated against the 331 baseline and **every** difference explained.

---

### S4 — Runtime cleanup (serial)

- **Remove `cv workspace backup` and `restore`**: `runtime/backup.py`, both subparsers
  (`cli/parser.py:99-107`), and their handlers. Update the tests in
  `tests/test_workspace.py` and `tests/test_fact_lifecycle.py` that cover them.
- `runtime/workspace.py:119` returns `state_root / "applications.sqlite3"`. A Postgres
  database is not a file in the Workspace. Rework this so the Workspace describes its
  roots and the database is addressed by URL. **Do not leave a phantom path.**
- `PRAGMA integrity_check` / `foreign_key_check` have no Postgres equivalent in that form.
  The `ready` command reports `database_integrity` — keep that check meaningful or state
  plainly what it now verifies. **Do not report `true` for a check that no longer runs.**

**Two architecture tests will fail. Fix them; do not delete them.**

- `tests/test_architecture.py:353` `test_sqlite_and_sql_are_owned_by_persistence` — bans
  `import sqlite3` and `PRAGMA` outside persistence. Repoint it at SQLAlchemy/psycopg so
  it still proves persistence is sealed. Keep `PERSISTENCE_KNOWN_OFFENDERS` empty; a new
  entry is a stop condition.
- `tests/test_architecture.py:402` `test_numbered_migrations_are_registered_once` —
  checks `*.sql` against the old runner. Replace it with the Alembic equivalent (one head,
  no duplicate revisions).

Deleting a guard is not fixing it.

**This is the one boundary on §6.1.** Dead *implementation* is deleted; a *guard* whose
subject changed is repointed, never removed. A test that exists only to exercise a deleted
mechanism (the backup/restore tests) does go — that is dead implementation coverage, not a
guard. If you cannot tell which side a test falls on, stop and ask (§7).

---

### S5 — Documentation (serial)

Now, and only now, edit `docs/`. The user chose: **`CLAUDE.md` is updated and stays the
source of truth** — it is not frozen and replaced.

- `CLAUDE.md`: PostgreSQL/SQLAlchemy/Alembic become the baseline; drop the PostgreSQL
  non-goal; correct the offline-CLI rule to reflect the Postgres requirement; remove the
  `cv workspace backup` control at L116-118 **and** its reference at L184, which lists it
  as one of three derived checks replacing the retired Migration-safety section. Leaving
  L184 pointing at a deleted command is exactly the dangling contradiction `CLAUDE.md`
  warns against.
- `docs/v2/spec/architecture.md`: rewrite §6.1 and §2's dependency baseline.
- `docs/v2/smoke-run.md`: add the Postgres prerequisite.
- **Do not** edit anything under `docs/v2/records/` or the frozen `m2/m3/m4-remaining.md`
  trackers.

Also note in `CLAUDE.md`'s own "Keeping this file small" section which control was retired
here — the file requires that at each closing boundary.

---

## 6. Translation rules

1. **Behaviour is preserved exactly.** Same rows, same order, same errors, same
   transaction boundaries. This is a mechanical translation, not a redesign.
2. **`ORDER BY` is never dropped.** Several queries end `ORDER BY version_number DESC
   LIMIT 1` — that ordering *is* the correctness.
3. **Errors keep their taxonomy.** `UnknownRecord` and friends must still be raised from
   the same conditions (`test_persistence_refuses_through_the_application_taxonomy`
   asserts this).
4. **Immutability failures stay failures.** A write to an immutable table must still
   raise. Surfacing a Postgres error where a SQLite one used to appear is fine; silently
   succeeding is not.
5. **No opportunistic refactors.** No renames, no signature "improvements", no reordering
   of unrelated code. `CLAUDE.md`: "Do not perform unrelated refactors or cleanup."
6. **Parameter binding everywhere.** No string interpolation into SQL.

---

## 6.1 Delete what the change makes dead. No legacy, no compatibility layer.

**This is a replacement, not an addition.** When SQLAlchemy takes over a
responsibility, the code that used to hold it is deleted in the same stage — not
deprecated, not left "just in case", not kept behind a flag.

There is **nothing to be backward-compatible with**. There is no data, no other consumer,
no released version, and no second dialect. SQLite is not a fallback — it is gone.

**Delete outright:**

- `sqlite3` imports, `connect()`, `memory_connection()`, `backup_database()`, and every
  `PRAGMA`.
- `SqliteUnitOfWork`, `SqliteRepositoryBase`, and every `Sqlite*` class name. The
  replacements take the role; the originals do not survive beside them.
- `schema.py` — the whole in-repo migration runner: `SCHEMA_VERSION`,
  `REGISTERED_MIGRATIONS`, `registered_migration_names()`, the fingerprint machinery, and
  the `SchemaError` family that only it raised. Alembic replaces all of it.
- `infrastructure/persistence/migrations/*.sql` — both files.
- `runtime/backup.py` in full, plus both CLI subparsers and their handlers.
- Any helper, import, constant, or error class left with no caller after the above.

**Explicitly forbidden:**

- A compatibility shim, adapter, or alias mapping an old name to a new one.
- A `if dialect == "sqlite"` branch, or any dialect switch.
- Keeping a `Sqlite*` name as an alias "so nothing breaks".
- A dead function left in place with a comment saying it is unused.
- Commented-out old SQL kept "for reference". Git has it.
- A config setting, env var, or CLI flag whose only purpose was SQLite.

**How to be sure something is dead before deleting it:** grep for the symbol across
`cv_engine/` **and** `tests/`. No callers means delete. If the only remaining caller is a
test that exists solely to test the deleted mechanism, the test goes too — say so in the
report and explain what coverage was lost, if any.

If deleting something would change observable behaviour, that is a §7 stop condition —
ask, do not keep it quietly.

The one exception: the naming and shape required by `application/ports/` (§2). That is the
contract, and it stays.

## 7. Stop and ask — do not guess

`CLAUDE.md` and `execution-protocol.md` §8 both make stopping the expected behaviour, not
a failure. In a 3,151-line mechanical rewrite, **a wrong guess is worse than a question**:
a mistranslated `WHERE` will not fail a test and will surface as a logic bug weeks later.

Stop and ask when:

- you cannot tell what a piece of SQL is meant to do;
- a column's intended Postgres type is ambiguous;
- preserving behaviour would require changing a `ports/` signature;
- a test asserts on something the change would alter;
- `PERSISTENCE_KNOWN_OFFENDERS` would need a new entry;
- SQLite and Postgres genuinely differ in a way that changes observable behaviour
  (e.g. `NULL` ordering, `TEXT` comparison/collation, integer division, implicit type
  affinity);
- any acceptance criterion cannot be honestly ticked.

State the problem and its consequences, then wait.

---

## 8. Acceptance

The task is done when **all** of these hold:

1. `grep -rni "sqlite" cv_engine/ tests/` returns nothing — no imports, no class names, no
   dialect branches, no leftover comments. Same for `PRAGMA`, `Sqlite`, and
   `backup_database`.
1b. No compatibility shim or alias exists anywhere (§6.1), and `schema.py`,
   `migrations/*.sql`, and `runtime/backup.py` are deleted, not emptied.
2. `grep -rn "sqlalchemy\|psycopg" cv_engine/application/ cv_engine/domain/ cv_engine/api/`
   returns **0**.
3. `alembic upgrade head` builds all 22 tables on an empty database.
4. Every immutable table rejects UPDATE and DELETE; the exception set is explicit.
5. `./.venv/bin/python -m pytest -m "not browser"` passes, reconciled against the 331
   baseline with every difference explained.
6. `tests/test_architecture.py` passes with both rewritten guards, `PERSISTENCE_KNOWN_OFFENDERS`
   still empty.
7. **`docs/v2/smoke-run.md` reaches `preparation_state: ready` against Postgres.** This is
   the real acceptance test — a green suite is not enough.
8. Frontend: still 156/156, untouched.
9. `CLAUDE.md` and `architecture.md` updated; no dangling reference to `cv workspace
   backup` or SQLite.

---

## 9. Reporting

Per `CLAUDE.md`: **never claim completion with "implemented" alone.** Report what passed,
what failed, and what remains. A hard failure is never relabelled a warning.

For each stage, hand back:

- the commits and their diffs (small, intentional, no unrelated changes mixed in);
- the ordered commands, each using `./.venv/bin/python`, with what it proves and what a
  pass looks like;
- the predicted test count and an explanation for every deviation from it;
- **what you deleted** (§6.1), and confirmation that nothing was left as a shim, alias, or
  dead-but-present function;
- anything you could not verify because you did not run it — state it plainly.
