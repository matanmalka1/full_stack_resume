# Storage maintenance backlog

## Safe orphan deletion

Status: OPEN — separate from the completed persistence architecture refactor.

Approved scope clarification, 2026-09-17: read-only orphan inspection closes the
persistence refactor; deletion is a separate task. The inspection contract lives in
[`../spec/state-and-use-cases.md`](../spec/state-and-use-cases.md), section 19b.

A payload is written before database registration. An inspection candidate may belong
to an active writer awaiting registration, including one that registers after the
inspection snapshot. A grace period alone cannot establish safe deletion.

Before implementing deletion, specify coordination with active writers and evidence
that a payload is not awaiting registration. Preserve every registered snapshot,
revision, historical artifact, and inactive output. Do not add leases, tombstones,
registration intents, or another coordination mechanism without that design.
