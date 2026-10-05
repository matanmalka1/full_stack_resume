# Proposal: Knowledge in PostgreSQL, ahead of accounts

Status: **proposed, not approved** (2026-10-05). Nothing here is binding until it is
approved and the specifications are changed (§7). It changes only the *order* and the
*first shape* of a step [`multi-user-accounts.md`](multi-user-accounts.md) already
approved: decision 7 there ("Knowledge moves to PostgreSQL") and delivery step 3.

## תקציר

היום עובדות, CandidateContext והשיוך של עובדות לפרופילים יושבים בקבצים, וכל שאר
המצב ב־PostgreSQL. לכן כל שינוי בעובדה חוצה שני מקומות אחסון, ובשבילו קיים מנגנון
שלם של journal, staging, שחזור בעלייה ו־quarantine. ההחלטה על ריבוי משתמשים כבר
קבעה שהמנגנון הזה ייעלם כשהעובדות יעברו ל־DB. ההצעה: לבצע את המעבר **עכשיו, כצעד
של מועמד יחיד**, בלי לחכות לטבלאות משתמשים וסשנים, ולשמור על אותה נוסחת גרסה כך
שאף מסמך קיים לא ייפסל. ההצעה גם מצביעה על סתירה במפרט היעד (§4) ועל יכולת אחת
שתאבד: עריכה ידנית של קבצי העובדות והפרופילים (§5), שדורשת החלטה.

## 1. Why now

A fact mutation crosses a file and the database, so it runs a two-phase protocol
(architecture §7.2, product-spec §17): stage the file, write a `PREPARED` journal row,
replace the file, commit the fact events with `COMMITTED`, clean up. Crash recovery
runs at composition and decides from hashes whether to finish, restore, or
quarantine; a quarantined entry blocks every fact mutation and every approval.

Every Knowledge read pays for it as well: `CommittedKnowledge` opens a read scope to
check for a `PREPARED` entry before each load, and Operation handlers check through
their own token.

What exists only for that protocol:

| Where | What |
| --- | --- |
| `application/services/knowledge/mutations.py` | the prepare/complete/restore/quarantine/recover engine (254 lines) |
| `application/services/knowledge/committed.py` | `CommittedKnowledge`, `refuse_prepared_knowledge` |
| `application/knowledge_mutations.py` | `KnowledgeMutation`, `StagedKnowledgeFile`, `KnowledgeFileState`, `PrepareKnowledgeMutation` |
| `infrastructure/knowledge.py` | `stage_*`, `activate_staged`, `restore_staged`, `discard_staged`, `staged_file_state`, fsync helpers |
| `infrastructure/persistence/knowledge_lifecycle.py` | journal reads and transitions |
| `application/services/drafts/review.py` | approval refused while an entry is quarantined |
| `runtime/composition.py` | `KnowledgeRecoveryService(...).recover_knowledge_mutations()` at startup |
| `tests/knowledge/test_fact_lifecycle.py` | crash, restore, and quarantine tests |

The approved target already retires all of it. Today it sits behind delivery step 2
(users, sessions, bootstrap CLI), which the Knowledge move does not need: a single
candidate has one owner by definition. Doing the move first removes the most
intricate non-regenerable code path in the system, whether or not the rest of the
multi-user plan is ever built.

## 2. Proposal

1. **Move facts, CandidateContext, and Profile bindings to PostgreSQL as one step,
   single-candidate.** Same tables as architecture §18.2, without `user_id`:
   - `facts`: `UNIQUE (fact_id)` instead of `UNIQUE (user_id, fact_id)`.
   - `candidate_contexts`: one row, guarded the way `app_settings` is today
     (`singleton_id`).
   - `profile_bindings`: primary key `profile_id`.
   - `fact_sources` (new, see §4): `source`, `source_version`.

   Profile *templates* (track, sections, `max_claims`, emphases, tag weights) stay in
   `profiles/`. Section pools, pins, `safe_headlines`, and `omitted_roles` move to the
   binding. The binding has to move in the same step: `attach_fact` and
   `confirm_and_use_fact` write a Profile file today, so leaving it behind keeps the
   journal alive.
2. **A fact mutation is one write scope.** The fact row (or binding row) and its fact
   events commit together. No staging, no journal, no recovery, no quarantine.
3. **`import-knowledge`** (operator CLI) reads `base/*.json`, `base/candidate.json`,
   and the candidate-specific parts of `profiles/*.yaml` and `profiles/sales/*.yaml` in
   one transaction. It refuses when any fact exists. Fact IDs, statuses,
   `confirmed_at`, `replaces`, `source`, and in-source order are copied exactly. It
   recomputes `FactStore.version` and `lifecycle_version` from the database and rolls
   back unless both equal the values computed from the files.
4. **Ownership comes later, with the same rule as Applications.** Delivery step 4
   (`applications.user_id`) also adds `user_id` to `facts`, `candidate_contexts`,
   `profile_bindings`, and `fact_sources`, assigns the one user, and swaps the
   constraints to the §18.2 form. It refuses unless the user count is exactly one,
   the same precondition it already has for Applications.
5. **The journal table stays as read-only history.** The revision that ships this step
   refuses to upgrade while any entry is `PREPARED` or `QUARANTINED`; the operator
   resolves it on the old version first (as decision §4.6 already says).

## 3. Rejected alternatives

- **Keep the order: users first, then Knowledge.** Step 2 ships `user_sessions`,
  `auth_events`, and `set-password` with no route that uses them until step 7. The
  Knowledge move gains nothing from them, and the journal lives on in the meantime.
- **A minimal `users` table now, just to own facts.** It forces a `create-user` before
  a single-candidate installation can import its own facts, for an owner that cannot
  be anyone else.
- **Facts in PostgreSQL, bindings left in files.** `attach_fact` would still cross
  stores, and the journal would stay for that one command.

## 4. Specification conflict: the fact-store version

Architecture §18.2 says: "Each fact mutation increments the user's
`fact_store_version` … It replaces today's per-file `source_version` as the coarse
version a Submission's content records."

That conflicts with existing behavior:

- `FactStore.version` (`domain/facts.py`) covers **canonical facts only**, on purpose:
  creating or confirming a `pending` fact for one Application must not invalidate
  another Application's approved draft.
- Validation compares it with the draft's `fact_store_version`
  (`domain/validation.py`, `fact-store-version-mismatch`), and a failed check blocks
  approval.

A counter that moves on *every* mutation would therefore make every document fail its
content check whenever any pending fact is created. Replacing the hash with any other
value also fails every existing unsubmitted document once, at upgrade.

**Proposed resolution:** keep the version derived, not stored. `FactStore.version`
and `lifecycle_version` keep their current formula, computed from the `facts` rows
and the `fact_sources` versions; `source_version` keeps its current bump rule
(`_next_source_version`, canonical changes only). No counter column. The import proves
equality (§2.3), so no existing document's validation changes at upgrade. This also
follows the project's own rule to derive a value rather than maintain it.

§18.2 should be amended to match before step 4 is built, whether or not this proposal
is approved.

## 5. What is lost: hand edits — needs a decision

Product-spec §17 says today: "Hand edits to the Knowledge files are supported." After
the move, `base/` and the candidate-specific parts of `profiles/` become import input
only, as the approved target already states. For the current single candidate that
removes:

- **Fixing a fact's content.** Already a non-goal on the Web; the lifecycle route is a
  correction (`replaces`) and confirm, which keeps working.
- **Removing a fact from a section pool, reordering a pool, or unpinning.** There is no
  command for any of these; `attach_fact` only adds. Today this is done by editing the
  YAML.
- **Changing `safe_headlines`, `omitted_roles`, or CandidateContext fields.** Only
  `import-knowledge` writes them, and it refuses a non-empty store.

Options:

1. **Accept the loss** until a need shows up. Smallest change; matches the approved
   target. Pool tuning stops being possible without SQL.
2. **Add `detach_fact` and `pin`/`unpin`** to the fact surface. Small, journal-free
   commands now that a binding change is one write scope, but a scope addition
   (product-spec §5 forbids Web editing of Profiles; these touch only the binding,
   like `attach_fact`).
3. **An operator `export-knowledge` / `replace-binding` pair** for structured edits
   from a file. Keeps the YAML workflow for the operator without a second runtime
   source of truth.

Recommendation: **2 for pools and pins** (it is what hand edits are used for in
practice), **3 deferred** until headlines or CandidateContext actually need to change.

## 6. Delivery

Each step is its own pull request with its focused gates (`CLAUDE.md`).

1. **Specs and records.** This proposal approved; §7 applied. Documentation only.
2. **Schema, import, and the switch.** Tables, `import-knowledge`, a PostgreSQL
   `KnowledgeStore` behind the existing port, fact mutations as one write scope, the
   template/binding split of `profiles/`. Reads and writes switch together: a store
   cannot read from the database while mutations still write files. The test seed
   (`tests/knowledge_seed.py`) imports into the database instead of copying files.
3. **Retirement.** Delete the journal engine, `CommittedKnowledge`, the staging
   adapter, startup recovery, the quarantine approval block, and the journal fields in
   the maintenance report. Pure deletion after step 2 has proved itself.
4. **`detach_fact`, `pin`/`unpin`** if option 2 is approved.

Then the multi-user order resumes from its step 2, with step 4 extended as §2.4
describes.

**Gates.** Step 2 is a schema change and changes a stored value's source, so it owes
the migration-topology and empty-database upgrade checks with the schema diff, the
fact-lifecycle and persistence-constraint tests, and
`tests/e2e/test_pipeline_end_to_end.py` against a fresh database. Golden hashes must
not move: the same facts render the same output. The import's version-equality check
runs against the repository's own `base/` as well as the test seed.

## 7. Specification changes on approval

- `CLAUDE.md`: "`base/` and `profiles/` hold the live source facts" becomes the
  database, with `base/` as import input.
- product-spec §3 and §17: the file mechanism and "hand edits are supported" removed;
  the *designed, not built* note on Knowledge becomes current behavior, minus
  ownership.
- architecture §6.3 and §7.2: Knowledge files reduced to policy; the journal section
  becomes history. §18.2: the counter replaced as in §4, and `user_id` added in step 4.
- state-and-use-cases §17 and §19b: quarantine refusals and journal counts removed.
- test-and-acceptance-plan: journal recovery evidence replaced by the import-equality
  check.
- `multi-user-accounts.md` §4 and §5: Knowledge moved ahead of users; step 4 extended.
