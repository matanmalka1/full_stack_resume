# Execution Protocol — lead agent and parallel executors

Status: **Active working protocol (2026-09-29)**

Use this protocol when implementation is split across agents. It covers coordination,
file ownership, integration, and evidence handoff for refactors, features, and fixes.
Use one agent when the work does not justify parallel lanes (section 7).

This document grants no authorization. [AGENTS.md](../AGENTS.md) governs agent work,
including who runs tests and which gates a diff owes. The [specifications](README.md)
govern product behavior. Those rules apply to every lane; this document adds only the
coordination rules below.

## 1. Roles and assignment

| Role | Owns | Limits |
| --- | --- | --- |
| **Lead** | Scope, lane contracts, ownership, sequencing, integration, evidence review, and stop decisions | Cannot authorize a product deviation the user owns |
| **Executor** | Implementation within one lane's declared files and approved behavior | Escalates changes to scope, behavior, interfaces, or ownership; never edits another lane's files |
| **Reviewer** (optional) | Read-only audit of the diff and acceptance evidence | Reports findings; does not edit files |

Before dispatch, the lead declares the common baseline commit, each lane's owned and
readable paths, any lead-only paths, expected behavior, interface strategy, acceptance
criteria, focused checks, runtime resources, and merge order. Link the owning specification
for an intended behavior change. Executors may make internal implementation choices within
that contract; unresolved product decisions return to the lead and, when necessary, the user.

## 2. Waves and evidence handoff

| Wave | Owner | Work |
| --- | --- | --- |
| 0, only when needed | Lead | Prerequisite guards or deletions that lanes must build on |
| 1 | Executors | Disjoint packages under the declared contracts |
| 2 | Lead | Integration, removal of temporary shims, and boundary evidence review |
| 3, only when required | Lead and user | An action requiring approval that has not already been given |

Use wave 0 only when enforcement must exist before lane changes, or a prerequisite deletion
prevents lanes from depending on code being removed. Otherwise start at wave 1. Establish
the lanes' common baseline after prerequisite changes. Approval requirements come from the
applicable instructions or task, not from the existence of wave 3.

A dependent wave waits for the prerequisite's required evidence. Locally, agents prepare
focused commands and the user runs them; the cloud exception and its setup requirements
are defined in AGENTS.md. A handoff may say **changes ready; verification pending**, with
exact commands and outstanding checks. It must not claim a pass or verified completion.
Independent work may continue while results are pending.

At boundary close, hand over the scoped gates once, in order, explaining what each proves.
Parallel work does not itself require a full suite. AGENTS.md determines scope and any
additional evidence; broaden only for a stated reason.

## 3. Exclusive ownership and runtime isolation

Each path has one owner during a wave. Derive lanes and any lead-only set from actual
coupling: shared fixtures, composition roots, and other hubs are not automatically
lead-only. If a lane needs an unowned file, it pauses that edit and asks the lead to assign
it. If another lane owns it, the lead records a transfer before work resumes, moves the
edit to integration, or stops the affected package. Ownership must never overlap.

A worktree isolates files, not runtime resources. For checks that use them, give each
concurrent lane its own database, payload tree or object-store prefix, temporary and
rendered output directories, and bound ports. Provision only what that lane uses.
When a resource cannot be isolated, serialize the operations that use it; independent
editing can remain parallel if file ownership and contracts stay disjoint.

## 4. Interfaces between lanes

Declare cross-lane interfaces before implementation. If a feature or fix cannot expose a
stable contract for independent work, sequence the dependent packages.

For symbol moves with importers outside the lane, preserve the old import surface during
wave 1 using an explicit temporary re-export, for example:

```python
from .new_owner import moved_symbol  # temporary re-export: removed in Wave 2
```

The lead removes these shims and updates cross-lane callers during integration. If one lane
owns the move and all importers, it may update them directly and prove the old path unused.
State the chosen strategy in the lane contract. A shim must not hide an unapproved behavior
or public-interface change.

## 5. Worktrees and integration order

- Each lane uses its own branch and worktree at the declared common commit. Executors do
  not commit to the long-lived branch.
- Reuse a worktree only after checking its baseline and confirming it has no staged,
  unstaged, or untracked residue. Preserve existing user work when preparing the baseline;
  never clean it away to make a lane usable.
- Executors do not rebase, squash, force-push, or run interactive Git operations.
- The lead integrates in the declared order and inspects each resulting diff. Select
  post-merge checks from the coupling actually affected, following AGENTS.md's execution
  rules. A merge is not an automatic reason to repeat a lane's entire subset.

## 6. Acceptance and reporting

### Per lane

The handoff identifies the baseline and resulting commits, intended behavior changes,
remaining work, and passed, failed, or pending checks. Quote actual command results when
available; never substitute expected output for evidence.

Verify the complete changed-path set against declared ownership. For a lane still based on
its assigned baseline, use `git diff --name-status <baseline>` for tracked changes, including
committed, staged, and unstaged work, and `git ls-files --others --exclude-standard` for
untracked files. A plain `git diff --stat` can omit committed and staged work. Read the diff,
not just the path list.

Architecture checks protect code boundaries; they do not enforce lane ownership. Include
relevant guards when the affected behavior owes them, rather than imposing a backend
architecture test on every lane. Existing exception lists must not grow to accommodate a
lane's new violations.

For a refactor, report whether observable behavior and contracts were preserved. For a
feature or fix, identify the approved differences and verify that unrelated behavior was
preserved. Importer coverage belongs to the lane when it owns all callers, and to integration
when cross-lane callers were deliberately deferred. A lane is verified only when its
required evidence is available and passes.

### Lead integration

1. Review each lane's scope and evidence before accepting it; distinguish pending gates
   from failures and passes.
2. Integrate in order, reconcile cross-lane callers, remove every temporary shim, and
   search for remaining uses of retired import paths.
3. Review the combined diff against acceptance criteria and the owning specifications.
   Apply [semantic parity](spec/test-and-acceptance-plan.md#4-golden-matrix-and-semantic-parity):
   unexplained differences are failures; approved intended changes are assessed against
   their new contract.
4. Select the boundary's gates from the combined diff under AGENTS.md. Track which earlier
   evidence remains applicable and which checks the integrated changes still owe. Hand
   over local commands or report cloud results as required; do not mark pending checks done.
5. Record decisions or delivery state in `docs/tailoring-decisions.md` when relevant, and
   open defects or tasks in `docs/backlog/`. Closed trackers stay in Git history.
6. Report the result per package, including failures and anything still awaiting verification.

## 7. When to work serially

Use one agent when files cannot be owned disjointly, packages depend on unresolved changes
in one another, or coordination costs more than the work. Choose the number of lanes from
the dependency structure, not a target headcount. A reviewer is optional, not another
mandatory stage.

## 8. Stop conditions

AGENTS.md's stop conditions apply throughout. Pause the affected work and escalate when:

- a lane needs behavior or interface changes beyond its approved contract;
- a new architecture violation would require adding an exception;
- an ownership transfer would overlap or invalidate another lane's in-flight work;
- verification finds an unexplained semantic difference or an unmet acceptance criterion.

An approved behavior change is not a stop condition. A refactor that unexpectedly needs one
is. Do not weaken a test, refresh a golden, or change an acceptance criterion to conceal a
failure. If a criterion was over-scoped, explain and record the correction against the
approved scope; do not expand the task just to satisfy it.

## 9. Verify evidence without repeating it by default

The accepting side checks:

1. **Scope:** the commits exist, and the complete diff matches the claimed ownership and work.
2. **Implementation:** the claimed change is present in the code, not only in the report.
3. **Coverage:** compare test changes and counts with the baseline for the same selection;
   explain additions, removals, or deselections. Counts are a review signal, not a quota.
4. **Environment:** record the tested revision, local changes, commands, and relevant runtime
   isolation. Use the worktree's own dependencies and the [README setup](../README.md),
   including `./.venv/bin/python` for backend checks and frontend tooling where applicable.
   Another worktree's editable Python environment is not accepted as evidence for this one.

Request or perform a rerun, according to AGENTS.md, when evidence is missing or unreliable,
when affected code or conditions changed, or when a failure or concrete uncovered risk
requires it. Do not repeat a passing check under unchanged conditions merely because another
agent is accepting the work.

For a new or widened guard, or one whose target exists for the first time, include an
injected-violation probe to prove it can fail. Restore the probe afterward. This evidence
follows the same local/cloud execution rules as other checks and is owed once for that guard
change, not at every boundary. Guards derive their targets from code or schema; any necessary
exception list records existing debt explicitly and cannot grow to excuse new violations.
