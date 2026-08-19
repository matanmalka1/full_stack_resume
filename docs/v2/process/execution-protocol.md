# v2 Execution Protocol — lead agent and parallel executors

Status: **Active working protocol (2026-08-18)**

Scope: how multi-agent implementation work is organized in this repository. This document
describes the *process*; it grants no authorization and overrides no product document.
`CLAUDE.md` and the approved specifications remain authoritative, and every rule they
state applies to every lane. Only the multi-agent additions are written here.

It was derived from the M1 boundary refactor, which ran seven stages across three parallel
lanes and one integration wave without a single cross-lane conflict
(`docs/v2/records/architecture-audit.md` section 4 records what landed). Use it whenever
implementation is split across more than one agent. Skip it when one agent working serially
is the honest answer — see section 7.

## 1. Roles

| Role | Owns | Never does |
| --- | --- | --- |
| **Lead agent** | Sequencing, the shared/lead-only file set, integration, final verification, every judgment call and stop-condition decision | Delegate a judgment call to an executor |
| **Executor** | One lane's exclusive file set, mechanically | Touch another lane's files; decide behaviour; coordinate with another executor |
| **Reviewer** (optional) | Read-only audit of acceptance criteria; reports findings | Write anything; own any file |

Model allocation: strongest reasoning model as lead, mid-tier for executors, and the
reviewer sized to the audit's difficulty. The reasoning burden concentrates in guardrail
design and integration, which are lead-only.

## 2. Waves

A wave does not begin until the previous one is fully green.

| Wave | Who | Content |
| --- | --- | --- |
| 0 | lead, alone | Guardrails first, then any dead-code removal |
| 1 | executors, parallel | One work package per lane |
| 2 | lead, alone | Integration: remove temporary compatibility shims, repoint real call sites, full verification |
| 3 | lead, with the user | Anything approval-gated. Never folded into wave 2 |

Wave 0 is serial and first for a specific reason: it lands the enforcement that every lane
is then required to keep green, and it deletes symbols a lane might otherwise start using.
Guardrails written after the moves cannot fail on the moves.

Widened architecture rules land with an **explicit allowlist of known offenders**, so the
file records the debt and blocks new instances. Entries may be removed as debt is paid;
entries may never be added.

## 3. Exclusive file ownership

Each lane is defined by the paths it **owns**, the paths it may **read**, and the paths it
**must not touch**. Touching another lane's path is a protocol violation, not a merge
conflict to resolve later.

A **lead-only set** is declared up front and edited by nobody in wave 1. It is what makes
the parallelism safe, and it is derived from actual coupling rather than convenience —
typically the composition root, the CLI, shared test fixtures, and any hub module that every
lane would otherwise have to edit.

Lanes are derived from the coupling graph, not from a target headcount. If the work is
sequentially dependent, say so and run it serially.

## 4. The interface contract that makes wave 1 parallel

Every lane **preserves its module's existing public import surface for the whole of wave
1**, using an explicit temporary re-export in the module that used to hold the symbol,
marked so it cannot be mistaken for permanent:

```python
from .new_owner import moved_symbol  # temporary re-export: removed in Wave 2
```

Consequence: each lane's diff is confined to its own files, every lane branch is
independently green, and all cross-lane import churn happens exactly once — in wave 2, by
the lead. The shims are removed there; they never survive into the final state.

## 5. Git protocol

`CLAUDE.md`'s rules on small scoped commits, destructive operations, and isolated
Workspaces apply unchanged to every lane. What multi-agent work adds:

- One git worktree per lane, all based on the same commit. No executor commits to the
  long-lived branch.
- Create lane worktrees fresh per milestone. A stale lane worktree silently builds on the
  wrong baseline.
- Executors never rebase, squash, force-push, or run interactive git.
- The lead merges in a fixed, declared order, running that lane's subset plus the full suite
  after each merge.

## 6. Definition of done

### Per lane

A lane reports done only when all of these hold, with command output quoted:

1. Its own declared test subset passes.
2. The full suite passes.
3. The architecture test passes and its allowlist has **not** grown.
4. `git diff --stat` lists only files the lane owns.
5. An explicit statement of what did **not** change — for behaviour-preserving work: no
   threshold, message string, exception type, validation group name, status, callable
   signature, stored shape, artifact-path policy, or fact semantic. Message text is checked
   byte-for-byte, because tests match on it.
6. Anything not achievable mechanically is reported as a finding, **not** worked around. A
   lane that discovers it needs to change behaviour stops and reports.

Reporting follows `CLAUDE.md`: passed / failed / remaining, with command evidence.

### Lead integration

1. Merge in the declared order, testing after each merge.
2. Delete every temporary shim and repoint the real call sites.
3. Prove no module still imports a moved symbol from its old home (grep the old paths).
4. Full verification, including the browser-complete suite and the semantic-parity check.
5. Update the milestone's state record with what landed and what remains.
6. Report per package, with command evidence.

## 7. When not to use this

Parallel lanes are justified only when file ownership can be made disjoint. They are the
wrong shape when:

- the work converges on one shared file (M1's second round converged on
  `tests/conftest.py`, so it ran with a single executor);
- the packages are sequentially dependent (M2's boundaries are schema → records →
  projections → operations);
- the change is small enough that the coordination costs more than the work.

Saying "this does not need three lanes" is a valid and expected outcome of planning.

## 8. Stop conditions

`CLAUDE.md`'s stop conditions hold for every agent in every wave. Lane work adds these,
which are specific to moving code under exclusive ownership:

- a move cannot be made without changing behaviour, or a test asserts on something the
  change would alter;
- the architecture allowlist would need a **new** entry;
- a lane needs a file it does not own;
- the semantic-parity comparison reports any difference;
- an acceptance criterion cannot be honestly ticked.

Stopping is cheaper than a silent workaround, and it is the expected behaviour rather than a
failure. Three of M1's stops were substantive and two changed the plan.

## 9. Verification is independent of the report

An implementing agent's report is a claim; the accepting side reproduces it. At minimum:
the commits exist and their diffs match the claimed scope; the suite reproduces under an
interpreter that was verified to exist; the test count is compared against a pre-change
baseline, because a bare pass count cannot distinguish added tests from lost ones; and the
claimed structural change is present in the code.

The canonical interpreter for this repository is recorded in
`docs/v2/records/architecture-audit.md` section 6. Evidence produced under another worktree's
environment is not accepted.

If a blocker raised during verification turns out to be an over-scoped acceptance bar rather
than a real defect, correct the bar and record that it was over-scoped. Do not widen a
milestone to satisfy a criterion it never stated.
