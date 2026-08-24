import type { DraftFact, WorkingDraftFacts } from "../api/contracts";
import { Button } from "../ui/Button";
import { omissionReasonLabels, selectionOutcomeLabels } from "./draftLabels";

interface DraftFactPanelProps {
  busy: boolean;
  facts: WorkingDraftFacts | undefined;
  onInclude: (fact: DraftFact) => void;
}

/* A.4 frame 3's deterministic fact include control.

   Only facts the SelectionPlan actually ranked appear: `outcome` is null for anything no
   plan considered, and an include for such a fact would have nothing to act on. That is
   also what keeps this from becoming a Knowledge manager - the whole canonical pool is
   not on offer here, this draft's own accounting is. */
export const DraftFactPanel = ({ busy, facts, onInclude }: DraftFactPanelProps) => {
  const omitted = (facts?.facts ?? []).filter(
    (fact) => fact.outcome === "omitted" && fact.linked_claim_ids.length === 0,
  );

  if (facts === undefined) {
    return <p className="text-support leading-6 text-cv-text-muted">טוען את חשבונאות העובדות…</p>;
  }

  return (
    <section aria-labelledby="draft-facts-heading" className="flex flex-col gap-3">
      <h2 className="text-heading-sm font-semibold text-cv-text" id="draft-facts-heading">
        עובדות שלא נכללו
      </h2>

      {omitted.length === 0 ? (
        <p className="text-support leading-6 text-cv-text-muted">
          כל העובדות שתוכנית הבחירה שקלה נכללות בטיוטה.
        </p>
      ) : (
        <>
          <p className="text-support leading-6 text-cv-text-muted">
            הכללה של עובדה קובעת אותה במפורש ובונה את הטיוטה מחדש. שאר ההחלטות שכבר נקבעו נשמרות.
          </p>
          <ul className="flex flex-col gap-3">
            {omitted.map((fact) => (
              <li
                className="flex flex-wrap items-start justify-between gap-3 rounded-surface border border-cv-border bg-cv-surface p-4"
                key={fact.fact_id}
              >
                <div className="max-w-prose">
                  <p className="text-body text-cv-text" dir="auto">
                    {fact.text ?? "לא ניתן לקרוא את העובדה הזו מהידע."}
                  </p>
                  <p className="mt-1 text-support text-cv-text-muted">
                    {selectionOutcomeLabels[fact.outcome ?? "omitted"]}
                    {fact.reason === null || fact.reason === undefined
                      ? ""
                      : ` · ${omissionReasonLabels[fact.reason]}`}
                    {fact.section === null || fact.section === undefined
                      ? ""
                      : ` · ${fact.section}`}
                  </p>
                </div>
                <Button
                  disabled={busy || fact.text === null}
                  onClick={() => onInclude(fact)}
                  variant="secondary"
                >
                  הכללת העובדה
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
};
