# M2 §4.5 Knowledge consistency — close-out record

Status: **closed and frozen** at handoff commit `122b957`.

This record covers the Knowledge-consistency boundary in
`docs/v2/spec/implementation-plan.md` §4.5 and the corresponding §4.7 item 5 acceptance
evidence. It does not authorize migration of live v1 data.

## Delivered boundary

- Additive migration `0010_knowledge_mutation_journal.sql` and guarded journal transitions from
  `PREPARED` to `COMMITTED` or `QUARANTINED`, with durable mutation and database identities.
- Validated staging, hashing, atomic replacement, and hash-safe restoration of complete Knowledge
  documents inside an isolated Workspace.
- Startup recovery and explicit reconciliation that finish, restore, or quarantine an interrupted
  mutation without inventing a fact or exposing uncommitted state.
- Knowledge lifecycle commands journal pending creation, claim capture, confirmation, canonical
  promotion, and Profile attachment, with immutable audit events.
- `confirm_and_use_fact` validates and journals fact promotion, Profile attachment, and immutable
  SelectionPlan creation as one logical mutation.
- Quarantine blocks dependent Knowledge mutations and approval while history, export, and tracking
  remain readable.
- Runtime Knowledge writers enter through the coordinator; only the explicit pre-Workspace fixture
  seeding helper remains outside it.

The implementation was split across `e30b2f4`, `c77ea44`, `9aaa855`, `707c53d`, and
`122b957`. No existing migration, immutable artifact, or live v1 data was changed or opened.

## Closing evidence

The user ran the supplied gate on 2026-08-19 from the project virtual environment.

| Gate | Result |
| --- | --- |
| Ruff and Pyright | clean; 0 type errors or warnings |
| Focused fact-lifecycle suite | 21 passed |
| Focused migration, journal, fingerprint, and schema-head set | 5 passed |
| Full non-browser suite | 242 passed, 4 browser tests deselected |
| Golden hashes and architecture | 7 passed, 1 browser case deselected |
| Browser-complete suite with `CV_REQUIRE_BROWSER=1` | 246 passed |

The increase from the previous 230-test browser-complete baseline is 16 collected cases: twelve
single-case tests plus four cases in the parameterized crash-window matrix. No test was removed.
The same delta explains the non-browser increase from 226 to 242.

The offline rehearsal used fresh test Workspace
`/private/var/folders/rt/yglsrkgn3zd05xb_fw2l4y980000gn/T/cv-45-verify.UdXTjw`, marked
`development` / `copy`, at schema head `0010`, with no `OPENAI_API_KEY`. The explicit flow
completed `ingest → analyze → draft → validate → approve → render → ready →
reconcile`; the PDF was one page, ATS claim coverage was `1.0`, all eight render groups passed,
and reconciliation found no problems across five artifact versions. `cv fast` then reached Ready,
and the second reconciliation found no problems across ten artifact versions. Both reconciliations
reported zero prepared and zero quarantined journal entries.

## Acceptance consequence

The focused matrix exercises every required interruption window and proves deterministic finish,
restore, or explicit quarantine. Together with the clean isolated migration and full handoff gate,
§4.7 item 5 is closed. Backup and live-v1 migration safety remain owned by §4.6 and were not
entered by this work.
