# Decision: a fact is edited in place, not replaced

Status: **approved, not implemented** (2026-10-11). The specifications carry the rules,
marked *designed, not built* until it ships: [`product-spec.md`](../spec/product-spec.md)
§17, [`state-and-use-cases.md`](../spec/state-and-use-cases.md) §8 and §17, and
[`architecture.md`](../spec/architecture.md) §18.2. This record keeps why, what is
removed, and the order it lands in.

## 1. Why

A fact's content was immutable. A correction was a second fact carrying `replaces`;
confirming it raised `FACT_SUPERSEDED` on every document that used the original, and the
original stayed in the store beside it.

That machinery protected things the system already protects another way:

1. **What was sent.** A Submission keeps its own copy of the content, the HTML and the
   PDF, with their hashes. Nothing done to a fact reaches it.
2. **What was approved.** Approval and Ready are stamps on the document's basis, and the
   basis includes the hash of every fact the document depends on. Changing a fact moves
   the basis: the document is no longer approved, and the content check refuses wording
   whose review evidence names the fact as it was.
3. **What a fact used to say.** `fact_events` records the whole fact (`fact_json`) at
   every event. An edit is an event like any other.
4. **That a fact changes only when the candidate says so.** An edit carries the same
   explicit confirmation that `pending -> canonical` does.

What a replacement fact added on top was a second record per correction, a warning that
asked the user to do by hand what the basis already does, and a reference that had to
resolve. The installation's own Knowledge showed the cost: two facts replace v1 ids
(`legacy.team_size.3-4`, `legacy.revenue.30-yoy`) that exist in no fact source, so the
foreign key the per-user schema specified for `replaces` could not hold for real data.

`CLAUDE.md` never listed facts among the immutable records. What must not change is what
left the system, and that is untouched.

## 2. The model

- `edit_fact(fact_id, changes, confirm)` changes a fact's content in place: meaning,
  renderings, tags, provenance, effective dates, `resume_style`, link target. The
  `fact_id` and the source it belongs to never change.
- A `pending` fact is edited freely and stays `pending`. A `canonical` fact needs
  `confirm: true`, stays `canonical`, and its `confirmed_at` becomes the date of the edit.
  A `deleted` fact is not edited.
- Every edit appends a `fact_edited` event with the fact as it now is; the previous
  event holds it as it was.
- A document that depends on the fact is not written. Its basis moves, so it is no longer
  approved or Ready, and the content check refuses wording reviewed against the earlier
  content until it is reviewed again or regenerated.
- `replaces` is history only: imported facts keep the value they carry, and no command
  sets it. `FACT_SUPERSEDED` is removed.

## 3. Order

1. **Specs and this record.** Documentation only.
2. **Per-user Knowledge tables and `import-knowledge`**
   (`multi-user-accounts.md` §5, step 4): `facts.replaces` is plain text with no
   foreign key, and the database guards only a fact's identity (`id`, `user_id`,
   `fact_id`, `source`, `ordinal`, `created_at`) and refuses every delete.
3. **The switch to database Knowledge** (same step), which retires the journal.
4. **`edit_fact`** in the application layer, the API and the facts screen; creating a
   fact with `replaces` and the `FACT_SUPERSEDED` warning are removed in the same
   change. Built after the switch so it is one database write, not another journaled
   file mutation.

Until step 4 ships, the implemented behavior is the replacement model.

## 4. Rejected

- **Keep replacement and enforce `replaces` with a foreign key.** It refuses the
  installation's own facts, and the alternatives — dropping the two v1 references, or
  inventing legacy facts for them to point at — lose evidence or invent it.
- **Keep replacement with a separate column for v1 references.** A schema distinction to
  protect a warning the basis already makes redundant.
- **Return an edited canonical fact to `pending`.** The edit's own confirmation is the
  explicit attestation `pending -> canonical` asks for; a second step would ask for it
  twice.
