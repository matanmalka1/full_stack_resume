# Decision: AI chooses the facts; the engine only guards them

Status: approved (2026-09-30), being implemented on branch `ai-owned-selection`. The
specifications describe this model and are authoritative; this record keeps why, what
was removed, and what the engine still decides.

## 1. Why

The engine ranked every Profile fact (requirement tier, profile and emphasis tag
weights, keyword hits), filled each section up to a claim budget, enforced per-role
floors, and rescued required tags by eviction. AI could only add pins and exclusions on
top, and every overlay was re-validated against the same budgets and floors. Choosing
which facts answer a job is a semantic judgment: it is the same judgment
`docs/spec/product-spec.md` §2 already gives AI for requirement interpretation. The
budgets, tags, and floors were preferences expressed as hard refusals, and a draft that
missed one of them failed even when every fact in it was true.

## 2. The decision

`draft_resume` chooses the facts and words them in one call. It receives, per Profile
section, the whole pool of canonical facts with their renderings in the document
language, the structural facts that are always present, and the section's guidance. The
engine narrows what comes back; it never widens it.

**The engine checks, and each check is a hard refusal:**

1. The fact exists and is canonical.
2. The fact is in the pool of the Profile section it is placed in.
3. The fact has a rendering in the document language (`MISSING_FACT_RENDERING`).
4. Structure holds. Headings, dates, and contacts are always present. A role's title
   and dates stay with that role, and every bullet sits under its own role. No role
   heading is left without a bullet. Historical-title placement and section order are
   kept. Chosen facts are laid out in pool order.

**Guidance, sent in the request and never enforced:**

- Section claim budget (`max_claims`) and per-role ceiling (`max_claims_per_role`).
- Per-role minimums (`min_claims_per_role`, `min_quantitative_per_role`).
- Required and preferred tags, profile and emphasis tag weights, emphasis minimum
  coverage.
- Profile `pinned_fact_ids`.

## 3. Removed

- Engine ranking and selection (`build_selection`, scoring, floors, required-tag
  rescue, pin capacity).
- The document's `selection` manifest and `selection_policy_version`. A CVDocument is
  its analysis pin plus its content; the facts it uses are the facts its content links.
- The fact-selection panel, user pins and exclusions, `update_selection`, the
  `propose_selection` Operation, and the `propose_selection_plan` AI task. There is no
  user selection before drafting: the user edits the content afterwards, and any
  section claim may be removed.
- The selection step inside `create_draft`.
- Validation codes `section-budget-exceeded`, `pinned-fact-dropped`,
  `required-tag-uncovered`, `emphasis-coverage-low`, and `selected-fact-set-mismatch`.
- The `POLICY_CHANGED` warning. Emphasis policy is guidance, so a change to it
  invalidates nothing.

## 4. Consequences

- **Emphasis.** An Emphasis change from the matching form is a classification change,
  like Track, Profile, or language. It creates a new immutable JobAnalysis without
  calling the provider (user decision 2026-09-30). There is no in-place emphasis
  override on the document.
- **Confirm and use.** It confirms the fact and attaches it to the named Profile
  section. It no longer writes the document. The next draft or regeneration can use the
  fact.
- **`build_from_analysis`** re-pins the analysis and clears content and every stamp. It
  computes nothing.
- **Schema.** The baseline migration drops `cv_documents.selection` and
  `cv_documents.selection_policy_version`, and drops `propose_selection` from the
  Operation types. The database starts empty; there was no data to keep.

## 5. Supersedes

- [`single-document-model.md`](single-document-model.md) §5, the SelectionPlan
  allocation to `cv_documents.selection`. It also supersedes that record's Wave 3 note
  that "the engine still ranks".
- `tailoring-decisions.md` D9 and D10, where they make deterministic policy the
  selection authority.
