# Documentation map

Where the authoritative answer lives. One concept, one home; everything else links here.

| I need to know | Read |
| --- | --- |
| What the product does, what it refuses to do, and every invariant | [`spec/product-spec.md`](spec/product-spec.md) |
| A state value, a command's preconditions, an error code, an HTTP route | [`spec/state-and-use-cases.md`](spec/state-and-use-cases.md) |
| A layer boundary, storage layout, runtime config, process model | [`spec/architecture.md`](spec/architecture.md) |
| What evidence a change owes, the golden matrix, release gates | [`spec/test-and-acceptance-plan.md`](spec/test-and-acceptance-plan.md) |
| Why tailoring works the way it does, and what is still only designed | [`tailoring-decisions.md`](tailoring-decisions.md) |
| Open frontend UX work | [`backlog/frontend-ux.md`](backlog/frontend-ux.md) |
| How the manual live-provider run is executed and recorded | [`acceptance/live-provider-run.md`](acceptance/live-provider-run.md) |
| How to split implementation across parallel agents | [`execution-protocol.md`](execution-protocol.md) |
| How to run, build, and test the system | [`../README.md`](../README.md) |
| How agents work in this repository, and which gate a diff owes | [`../CLAUDE.md`](../CLAUDE.md) |
| Frontend tokens, theming, RTL rules | [`../frontend/docs/design-system.md`](../frontend/docs/design-system.md) |
| Frontend module boundaries and where server state lives | [`../frontend/src/features/README.md`](../frontend/src/features/README.md) |

## Authority

1. `spec/product-spec.md` — binding product semantics, scope, safety, observable behavior.
2. `spec/state-and-use-cases.md` — state, command, query, and permission contracts.
3. `spec/architecture.md` — the technical architecture that implements them.
4. `spec/test-and-acceptance-plan.md` — execution and evidence.

`CLAUDE.md` (symlinked as `AGENTS.md`) governs how agents work, not what the product
does. Where it names a gate, it is authoritative for that gate.

Everything outside `spec/` is a record or a work list. A record explains a decision; a
work list tracks open work. Neither overrides a specification, and a conflict between
one of them and a specification is a blocker, not an interpretation.

## What is not here

Closed milestone plans, superseded design drafts, the v1 archive, and completed review
and checklist reports are in Git history rather than in this tree. `tailoring-decisions.md`
section 6 names the commits for the plans that code docstrings still cite.
