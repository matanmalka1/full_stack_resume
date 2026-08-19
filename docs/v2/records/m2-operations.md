# M2 §4.4 Operations — close-out record

Status: **closed and frozen** at implementation commit `bfbd64d`.

This record covers the six Operations bullets in `docs/v2/spec/implementation-plan.md` §4.4
and the corresponding §4.7 item 4 acceptance evidence. It does not expand M2 scope or authorize
work on live v1 data.

## Delivered boundary

- Durable Operation, output, and bounded resource-lease records with atomic claiming,
  heartbeat, cancellation, interruption, safe failure metadata, and immutable terminal state.
- One shared two-phase runner for the low-concurrency worker and foreground CLI execution.
- Optimistic source checks before execution and activation, classified as `SOURCE_CHANGED`.
- One automatic retry for classified transient provider or browser failures; manual retry creates
  a new Operation linked to the immutable original.
- Inactive output registration before activation, preserving failed render evidence without
  making it current.
- Installation-scoped idempotent Operation creation and approval receipts. Approval reserves the
  immutable revision identity before writing payloads and recovers that exact revision after the
  database/payload crash window. Exact orphan payload reuse requires byte equality.
- Structured rotating technical logs kept outside safe client-facing failure detail.
- `analyze`, `draft`, `render`, and `fast` use the foreground runner; `operation show`, `cancel`,
  and `retry` expose the durable lifecycle without requiring FastAPI.

The implementation was split across `7400870`, `d0e54f1`, and `bfbd64d`. Migration
`0009_idempotency_receipts.sql` is additive. Existing immutable artifacts and historical v1 data
were not moved, overwritten, or opened.

## Closing evidence

The gate ran on 2026-08-19 from the project virtual environment.

| Gate | Result |
| --- | --- |
| Diff, Ruff, Pyright | clean; 0 type errors |
| Focused Operations/persistence/integration set | 67 passed |
| Full non-browser suite | 226 passed, 4 browser tests deselected |
| Golden hashes and architecture | 7 passed, 1 browser case deselected |
| `0001` adoption/upgrade and registered-head checks | 3 passed |
| Browser-complete suite with `CV_REQUIRE_BROWSER=1` | 230 passed |

The offline rehearsal used fresh test Workspace `/private/tmp/cv-44-gate.HwLNfr`, schema head
`0009`, and no `OPENAI_API_KEY`. The explicit flow completed
`ingest → analyze → draft → validate → approve → render → ready → reconcile`; the PDF was one
page, ATS claim coverage was `1.0`, Ready passed, and reconciliation found no problems across
five artifact versions. `cv fast` then reached Ready through the same Operation runner, and the
second reconciliation found no problems across ten artifact versions.

## Acceptance consequence

The existing WorkingDraft edit-version compare-and-swap supplies the storage primitive later
mapped to HTTP ETag/If-Match. Together with the evidence above, §4.7 item 4 — ETag,
idempotency, leases, cancellation, retry, and `SOURCE_CHANGED` — is closed. HTTP exposure remains
owned by M3 and is not part of this boundary.
