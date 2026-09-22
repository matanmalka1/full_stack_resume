# Storage maintenance backlog

## Safe orphan deletion

Status: DESIGNED, 2026-09-22 — coordination contract specified in
[`../spec/architecture.md`](../spec/architecture.md) §7.1 (mechanism) and
[`../spec/state-and-use-cases.md`](../spec/state-and-use-cases.md) §19b
(`inspect_orphans`/`reclaim_orphans` command contracts); implementation pending.

A write lease now reserves a payload's destination (a group key, such as one
ApprovedRevision's JSON+Markdown pair) before any bytes are written, under physical keys
scoped to that specific attempt_id. `reclaim_orphans` fences an expired lease first
(`pending -> reclaiming`, the same conditional update a genuine registration needs, so
the two serialize against each other), then checks - before deleting anything - that
the database holds no reference to that attempt's keys. Deletion follows only from that
check, not from fencing alone; fencing rules out a *future* registration, the check
rules out one that already happened. A second key with no lease row at all - including
one an old attempt's late `put` produces after an earlier call already deleted its lease
and files - gets the same pre-deletion check and is removed the same way. Together these
replace the grace-period approach this backlog item originally ruled out, which could
not distinguish an abandoned writer from a slow one.

The accepted remaining limitation: the object-store write itself is not fenced, only its
registration is. An attempt whose lease was reclaimed can still complete its `put` after
the fact, producing a transient orphan with no lease row of its own - the second case
above. Such an orphan can never be registered, because registration requires a live
lease row for its group key under the exact attempt_id that produced it, and none
exists, so it is always safe for a later `reclaim_orphans` call to remove.
`reclaim_orphans` is specified as a repeatable operation rather than a single exhaustive
pass for exactly this reason. A guarantee that one call removes every orphan would
require the object store itself to refuse a write once its lease is gone - a fenced or
conditional write keyed to lease validity, which `ObjectStore` does not implement today
(it refuses only an already-occupied key). That stays open as possible future work, not
a requirement this design fails to meet.
