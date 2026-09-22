# Storage maintenance backlog

## Safe orphan deletion

Status: DESIGNED, 2026-09-22 — coordination contract specified in
[`../spec/architecture.md`](../spec/architecture.md) §7.1 (mechanism) and
[`../spec/state-and-use-cases.md`](../spec/state-and-use-cases.md) §19b
(`inspect_orphans`/`reclaim_orphans` command contracts); implementation pending.

A write lease now reserves a payload's destination before any bytes are written, under a
key scoped to that specific attempt, and is fenced before `reclaim_orphans` removes
anything: fencing proves an expired attempt can never register, and re-checking the
database before deletion proves a removed payload was never referenced. Together these
replace the grace-period approach this backlog item originally ruled out, which could
not distinguish an abandoned writer from a slow one.

The accepted remaining limitation: the object-store write itself is not fenced, only its
registration is. An attempt whose lease was reclaimed can still complete its `put` after
the fact, producing a transient orphan with no lease of its own. Such an orphan can never
be registered - no code path registers a payload without first winning its lease for
that exact key - so it is always safe for a later `reclaim_orphans` call to remove.
`reclaim_orphans` is specified as a repeatable operation rather than a single exhaustive
pass for exactly this reason. A guarantee that one call removes every orphan would
require the object store itself to refuse a write once its lease is gone - a fenced or
conditional write keyed to lease validity, which `ObjectStore` does not implement today
(it refuses only an already-occupied key). That stays open as possible future work, not
a requirement this design fails to meet.
