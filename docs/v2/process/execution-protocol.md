# v2 Execution Protocol — lead agent and parallel executors

Status: **Active working protocol (2026-08-19)**

Scope: how multi-agent implementation work is organized in this repository. This document
describes the *process*; it grants no authorization and overrides no product document.
`AGENTS.md` and the approved specifications remain authoritative, and every rule they
state applies to every lane. Only the multi-agent additions are written here.

It was derived from the M1 boundary refactor, which ran seven stages across three parallel
lanes and one integration wave without a single cross-lane conflict
(`docs/v2/records/architecture-audit.md` section 4 records what landed). Use it whenever
implementation is split across more than one agent. Skip it when one agent working serially
is the honest answer — see section 7.

## 1. Roles

| Role | Owns | Never does |
| --- | --- | --- |
| **Lead agent** | Sequencing, any declared lead-only files, integration, final verification, every judgment call, and deciding that a stop condition has triggered | Delegate a judgment call to an executor; decide a deviation the user owns |
| **Executor** | One lane's exclusive file set, mechanically | Touch another lane's files; decide behaviour; coordinate with another executor |
| **Reviewer** (optional) | Read-only audit of acceptance criteria; reports findings | Write anything; own any file |

Model allocation: strongest reasoning model as lead, mid-tier for executors, and the
reviewer sized to the audit's difficulty. The reasoning burden concentrates in guardrail
design and integration. Those activities are lead-owned when the package needs them; they
are not mandatory phases for every package.

## 2. Waves

A wave does not begin until the previous one is green under its own gate. "Green" means
the focused tests for what changed — not a full-suite run per step. The change class's
gate runs once, when the boundary closes, over the merged tree.

| Wave | Who | Content |
| --- | --- | --- |
| 0 (when owed) | lead, alone | New, widened, or newly non-vacuous guardrails; dead-code removal that must precede lane work |
| 1 | executors, parallel | One work package per lane |
| 2 | lead, alone | Integration: reconcile cross-lane call sites, remove any temporary compatibility shims, then one full verification at the end |
| 3 | lead, with the user | Anything approval-gated. Never folded into wave 2 |

Wave 0 is used only when a package owes a guardrail under section 9, or when a deletion must
land before lanes start so they cannot depend on dead code. In that case it is serial and
first: the enforcement every lane must keep green has to exist before the moves it guards.
When existing guards already cover the change and no prerequisite deletion exists, start at
wave 1. Do not invent a guardrail phase to make mechanical work look staged.

Widened architecture rules land with an **explicit allowlist of known offenders**, so the
file records the debt and blocks new instances. The allowlist is populated once, when the
guard is created or widened, from the offenders that already exist. From then on entries
may only be removed as debt is paid: a new violation is a stop condition, never a new
entry.

## 3. Exclusive file ownership

Each lane is defined by the paths it **owns**, the paths it may **read**, and the paths it
**must not touch without reassignment**. Uncoordinated cross-lane edits are a protocol
violation, not a merge conflict to resolve later.

A **lead-only set**, if one is needed, is declared up front and edited by nobody else in wave
1. It is derived from actual cross-lane coupling rather than file category: a composition
root, CLI module, shared fixture, or hub is not automatically lead-only. A trivial edit may
be assigned to one lane when that keeps ownership disjoint.

If a lane discovers that it needs a file outside its ownership, it pauses that edit and
escalates to the lead. The lead may transfer that file's ownership, move the edit into wave
2, or stop the package if neither preserves disjointness. The transfer is recorded before
work resumes; two lanes never own the file at once.

Lanes are derived from the coupling graph, not from a target headcount. If the work is
sequentially dependent, say so and run it serially.

### Runtime isolation

A separate git worktree separates the *files*. It does not separate what the tests touch,
and that is what `AGENTS.md`'s concurrency rule is actually about: two lanes writing the
same PostgreSQL database/schema, object-store namespace, or rendered output race the test
runner, and the numbers
they report become meaningless without either lane failing. So a lane also gets its own:

- a separate git worktree, a dedicated PostgreSQL database, and a dedicated local
  payload tree or S3-compatible bucket prefix;
- temp roots and test output directories;
- any bound port, when a lane runs the API or a browser.

Anything a lane cannot isolate is shared state, and shared state means the lanes are not
disjoint. Say so and run those packages serially.

## 4. The interface contract that makes wave 1 parallel

When a move has importers outside the lane, the lane **preserves its module's existing public
import surface for the whole of wave 1** using an explicit temporary re-export in the module
that used to hold the symbol, marked so it cannot be mistaken for permanent:

```python
from .new_owner import moved_symbol  # temporary re-export: removed in Wave 2
```

This keeps each lane's diff confined to its own files and moves cross-lane import churn to
wave 2. The shims are removed there; they never survive into the final state.

The re-export is not required when all importers are in the same lane, or when one lane owns
the move and every affected importer without creating overlapping edits. In that case update
the importers once and prove the old import path is unused. The lane declaration states
which strategy it uses so integration does not assume a shim exists.

## 5. Git protocol

`AGENTS.md`'s rules on small scoped commits, destructive operations, and isolated
runtime resources apply unchanged to every lane. What multi-agent work adds:

- One git worktree per lane, all based on the same commit. No executor commits to the
  long-lived branch.
- A clean existing lane worktree may be reused when its baseline is the declared common
  commit and it contains no untracked or uncommitted residue. Otherwise create it fresh. The
  lead verifies both conditions before assigning work; convenience is not evidence of a
  valid baseline.
- Executors never rebase, squash, force-push, or run interactive git.
- The lead merges in a fixed, declared order. After each merge, run a smoke/import check plus
  any focused check justified by actual coupling introduced at that merge. Run the full
  relevant suite once, after the last merge. Re-run a lane's whole subset only when the merge
  changes something that subset exercised or section 9's evidence checks fail.

## 6. Definition of done

### Per lane

A lane reports done only when all of these hold, with command output quoted:

1. Its own declared test subset passes. When section 4's shim strategy is used, importer
   coverage is the lead's after merge, where the surface actually moves. When the lane owns
   all affected importers and updates them directly, its subset includes those importers.
2. The architecture test passes and its allowlist has **not** grown. This one check is
   per lane rather than per boundary, because it is what enforces exclusive ownership
   while lanes are still separate; the rest of the change class's gate belongs to the
   boundary.
3. `git diff --stat` lists only files the lane owns.
4. An explicit statement of what did **not** change — for behaviour-preserving work: no
   threshold, contracted message string, exception type, validation group name, status,
   callable signature, stored shape, artifact-path policy, or fact semantic. Message text is
   preserved byte-for-byte only when a specification, public interface, snapshot/golden, or
   deliberate test assertion makes it a contract. Incidental prose is not promoted to an API
   merely because it appears in the diff.
5. Anything not achievable mechanically is reported as a finding, **not** worked around. A
   lane that discovers it needs to change behaviour stops and reports.

Reporting follows `AGENTS.md`: passed / failed / remaining, with command evidence.

### Lead integration

1. Merge in the declared order, running the risk-based post-merge checks from section 5.
2. Delete every temporary shim and repoint the real call sites; where no shim was used,
   reconcile only the cross-lane call sites left to integration.
3. Prove no module still imports a moved symbol from its old home (grep the old paths).
4. One verification at boundary close: the gate for the boundary's highest change class
   under `AGENTS.md`, run over the merged tree, plus the semantic-parity check. For a
   Class B boundary that is golden hashes, the architecture test, and an offline CLI run
   on top of the non-browser suite; for Class C it adds the browser suite and a
   `0001`-only database upgrading cleanly to head. The browser suite is skipped only when
   the boundary cannot affect a rendering or browser path.
   This is not the re-run section 9 warns against — no lane produces a full-suite run, and
   the merged tree is not the tree any lane tested. It is the boundary's only full run, and
   the first one over the code as it will actually ship.
5. Update the current milestone tracker — `docs/v2/m4-remaining.md` — with what landed and
   what remains. It is the only record of state; the tracker moves with the milestone, and
   a document under `docs/v2/records/` is frozen evidence for a closed boundary that is
   never updated with later state.
6. Report per package, with command evidence.

## 7. When not to use this

Parallel lanes are justified only when file ownership can be made disjoint. They are the
wrong shape when:

- the work converges on one shared file (M1's second round converged on
  `tests/conftest.py`, so it ran with a single executor);
- the packages are sequentially dependent (M2's schema boundary had to land before
  records, and records before projections — while §4.4 Operations touches different
  tables and runs alongside §4.3; the current milestone tracker holds the current order);
- the change is small enough that the coordination costs more than the work.

Saying "this does not need three lanes" is a valid and expected outcome of planning.

## 8. Stop conditions

`AGENTS.md`'s stop conditions hold for every agent in every wave. Lane work adds these,
which are specific to moving code under exclusive ownership:

- a move cannot be made without changing behaviour, or a test asserts on something the
  change would alter;
- the architecture allowlist would need a **new** entry;
- a requested ownership transfer cannot preserve exclusive ownership or would invalidate
  another lane's in-flight work;
- the semantic-parity comparison reports any difference;
- an acceptance criterion cannot be honestly ticked.

Stopping is cheaper than a silent workaround, and it is the expected behaviour rather than a
failure. Three of M1's stops were substantive and two changed the plan.

## 9. Verification checks what a report cannot prove about itself

An implementing agent's report is a claim, and the accepting side checks it. Checking is
not re-running everything that already passed: a green suite re-run under the same
conditions produces no new information, and M1's evidence section is what excess looks
like — a fresh environment re-ran the browser-complete suite, the golden test, and the CLI
lifecycle, and an independent reviewer then reproduced the same runs a third time.

The accepting side checks the four things a report cannot establish about itself:

1. **The commits exist and their diffs match the claimed scope.** Read the diff.
2. **The claimed structural change is present in the code.** Grep for it; a report saying
   a symbol moved is not the symbol having moved.
3. **The test count against a pre-change baseline.** A bare pass count cannot distinguish
   added tests from lost ones.
4. **The environment the numbers came from.** The canonical interpreter is this
   worktree's dedicated environment, `./.venv/bin/python`, bootstrapped with
   `python3 -m venv .venv`, `./.venv/bin/python -m pip install -e '.[test]'`, and
   `./.venv/bin/playwright install chromium`. Evidence produced under another worktree's
   editable environment is not accepted, even when import-order guards prove that v2 won.
   (`docs/v2/records/architecture-audit.md` section 6 records where this rule came from;
   it is frozen at M1 close and is not the live authority.)

Re-run a gate only when one of those checks fails, when the report leaves a gate
unproduced, or when the environment of the original run is itself in doubt — which is
exactly what happened at M1, and is why that re-run was right and repeating it by default
is not.

A guard is worth more attention than a re-run: prove it fails on an injected violation.
A passing guard that cannot fail is the defect a second suite run will never find.

Inject once per guard, not once per boundary. The probe is owed when the guard is new, when
its scope changed, and when it stops being vacuous — a guard that early-returns while its
target does not exist passes green forever, so the first boundary where the target exists is
the only chance to catch it. Boundary 1 owed all three: the SQL guard was widened past
`infrastructure/` in wave 2, and two guards were inert until their targets landed. A guard
untouched since its own probe is owed nothing; re-injecting it is the ceremony this section
otherwise argues against.

If a blocker raised during verification turns out to be an over-scoped acceptance bar rather
than a real defect, correct the bar and record that it was over-scoped. Do not widen a
milestone to satisfy a criterion it never stated.
