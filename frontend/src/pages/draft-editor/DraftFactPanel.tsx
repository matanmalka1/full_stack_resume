import { Database, Plus } from "lucide-react";

import type { DraftFact, WorkingDraftFacts } from "../../api/contracts";
import { Button } from "../../ui/Button";
import { QueryState } from "../../ui/QueryState";
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
  const included = (facts?.facts ?? []).filter(
    (fact) => fact.outcome !== null && fact.outcome !== undefined && fact.outcome !== "omitted",
  );

  if (facts === undefined) {
    return <QueryState className="text-support leading-6" loading loadingLabel="טוען את חשבונאות העובדות…" />;
  }

  return (
    /* A section of the editor, marked by its heading and a rule - not a tinted panel
       holding a grid of tinted cards. The counts are the summary; the sentence that
       explained what the section is has moved into the one line that needs it, the one
       above the omitted facts a user can act on. */
    <section aria-labelledby="draft-facts-heading" className="flex flex-col gap-3 border-t border-cv-border pt-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-heading-sm font-bold text-cv-text" id="draft-facts-heading">
          <Database aria-hidden="true" className="size-4 text-cv-accent" />
          ביסוס עובדתי
        </h2>
        <p className="text-support text-cv-text-muted">
          {included.length} נכללו · {omitted.length} הושמטו
        </p>
      </div>

      {omitted.length === 0 ? (
        <p className="text-support leading-6 text-cv-text-muted">כל העובדות שתוכנית הבחירה שקלה נכללות בטיוטה.</p>
      ) : (
        <>
          <p className="text-support leading-6 text-cv-text-muted">
            הכללה של עובדה קובעת אותה במפורש ובונה את הטיוטה מחדש. שאר ההחלטות שכבר נקבעו נשמרות.
          </p>
          <ul className="flex flex-col divide-y divide-cv-border">
            {omitted.map((fact) => (
              <li className="flex flex-wrap items-start justify-between gap-3 py-2.5 first:pt-0" key={fact.fact_id}>
                <div className="min-w-0 max-w-prose flex-1">
                  <p className="text-body text-cv-text" dir="auto">
                    {fact.text ?? "לא ניתן לקרוא את העובדה הזו מהידע."}
                  </p>
                  <p className="mt-0.5 text-support text-cv-text-muted">
                    {selectionOutcomeLabels[fact.outcome ?? "omitted"]}
                    {fact.reason === null || fact.reason === undefined ? "" : ` · ${omissionReasonLabels[fact.reason]}`}
                    {fact.section === null || fact.section === undefined ? "" : ` · ${fact.section}`}
                  </p>
                </div>
                <Button
                  /* The row names the fact; the button says what happens to it. Its full
                     name stays in the accessibility tree, where the row is not read
                     alongside it. */
                  aria-label="הכללת העובדה"
                  className="min-h-9 shrink-0 px-3"
                  disabled={busy || fact.text === null}
                  onClick={() => onInclude(fact)}
                  variant="secondary"
                >
                  <Plus aria-hidden="true" className="size-4" />
                  הכללה
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
};
