import { Plus, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import type { DraftFact } from "@/api/contracts";
import { routePaths } from "@/app/routePaths";
import { Button } from "@/ui/Button";
import { Disclosure } from "@/ui/Disclosure";
import { cx } from "@/ui/cx";
import { emphasisLabels, omissionReasonLabels } from "@/features/preparation";
import type { ContentSummary, SelectionSummary } from "../model/draftOverview";
import { claimOriginLabels } from "../model/draftLabels";
import type { EditableDocument } from "../model/drafts.types";

/* How many left-out facts are listed before the reader asks for the rest. Most drafts
   leave out a handful; a long list pushed the document itself below the fold. */
const OMITTED_PREVIEW = 4;

interface DraftContentSummaryProps {
  busy: boolean;
  content: ContentSummary;
  draft: EditableDocument;
  onInclude: (fact: DraftFact) => void;
  selection: SelectionSummary;
}

const omittedDetail = (fact: DraftFact): string =>
  /* Joined from whatever resolved, rather than concatenated blind: both label maps are
     exhaustive against the schema this build was compiled against and say nothing about a
     server that has since learned another omission reason. */
  [fact.reason == null ? undefined : omissionReasonLabels[fact.reason], fact.section ?? undefined]
    .filter((part): part is string => part !== undefined && part !== "")
    .join(" · ");

/* How the content in front of the reader was produced, and what was swapped in and out.

   The draft is the result of two decisions the editor used to leave unsaid: which facts
   the selection took from the knowledge base for this role, and how each chosen fact
   became a line - as written, reworded for the role, or not backed at all. This says both
   in one place, above the lines they describe, and keeps the one action it can take
   itself: bringing back a fact the selection left out. Every number is the document's own
   accounting; nothing is re-derived from the pool. */
export const DraftContentSummary = ({ busy, content, draft, onInclude, selection }: DraftContentSummaryProps) => {
  const [showAllOmitted, setShowAllOmitted] = useState(false);
  const emphasis = draft.selection.emphasis_override ?? draft.selection.emphasis;
  const omitted = showAllOmitted ? selection.omitted : selection.omitted.slice(0, OMITTED_PREVIEW);

  const origins = [
    { key: "verbatim", count: content.verbatim, tone: "text-cv-success" },
    { key: "reworded", count: content.reworded, tone: "text-cv-text" },
    {
      key: "unsupported",
      count: content.unsupported,
      tone: content.unsupported > 0 ? "text-cv-blocker" : "text-cv-text",
    },
  ] as const;

  return (
    <section
      aria-labelledby="draft-content-heading"
      className="flex flex-col gap-4 border border-cv-border bg-cv-surface p-card-padding"
    >
      <div className="flex flex-col gap-1">
        <h2 className="flex items-center gap-2 text-heading-sm font-bold text-cv-text" id="draft-content-heading">
          <Sparkles aria-hidden="true" className="size-icon-md text-cv-accent" />
          איך נבנה התוכן
        </h2>
        <p className="text-support leading-6 text-cv-text-muted">
          עובדות נבחרו מהמאגר לפי ניתוח המשרה והדגש <span className="font-semibold">{emphasisLabels[emphasis]}</span>,
          ומהן נבנו השורות. כל שורה מסומנת לפי המקור שלה, ומתחת לכל שורה אפשר לראות את העובדה שממנה נבנתה.
        </p>
      </div>

      <dl className="grid grid-cols-3 divide-x divide-cv-border border-y border-cv-border py-3">
        {origins.map((origin) => (
          <div className="flex flex-col items-center gap-0.5 px-2 text-center" key={origin.key}>
            <dt className="order-2 text-caption text-cv-text-muted">{claimOriginLabels[origin.key]}</dt>
            <dd className={cx("order-1 text-heading-md font-bold", origin.tone)}>{origin.count}</dd>
          </div>
        ))}
      </dl>

      <p className="text-support leading-6 text-cv-text-muted">
        {selection.included === 1 ? "עובדה אחת נכנסה לקורות החיים" : `${selection.included} עובדות נכנסו לקורות החיים`}
        {selection.pinned === 0 ? null : <> · {selection.pinned} מהן נקבעו במפורש</>}
        {selection.omitted.length === 0 ? null : <> · {selection.omitted.length} נשארו בחוץ</>}
      </p>

      {draft.selection.proposed_by === "ai" ? (
        <div className="flex flex-col gap-1">
          <p className="text-support text-cv-text-muted">הבחירה הוצעה על ידי AI ונבדקה מול כללי הבחירה.</p>
          {draft.selection.proposal_rationale == null ? null : (
            <Disclosure summary="נימוק ההצעה">
              <p dir="auto">{draft.selection.proposal_rationale}</p>
            </Disclosure>
          )}
        </div>
      ) : null}

      {selection.omitted.length === 0 ? null : (
        <div className="flex flex-col gap-2 border-t border-cv-border pt-3">
          <div>
            <h3 className="text-support font-semibold text-cv-text">עובדות שנשארו בחוץ</h3>
            <p className="text-caption leading-5 text-cv-text-muted">
              הכללה קובעת את העובדה במפורש ובונה את הטיוטה מחדש. שאר ההחלטות נשמרות.
            </p>
          </div>
          <ul className="flex flex-col divide-y divide-cv-border">
            {omitted.map((fact) => (
              <li className="flex items-start justify-between gap-3 py-2" key={fact.fact_id}>
                <div className="min-w-0 flex-1">
                  <p className="text-support leading-6 text-cv-text" dir="auto">
                    {fact.text ?? "לא ניתן לקרוא את העובדה הזו מהמאגר."}
                  </p>
                  <p className="text-caption text-cv-text-muted">
                    {omittedDetail(fact)}
                    {omittedDetail(fact) === "" ? null : " · "}
                    <Link
                      className="font-semibold text-cv-accent hover:text-cv-accent-hover"
                      to={`${routePaths.facts}?fact=${encodeURIComponent(fact.fact_id)}`}
                    >
                      במאגר העובדות
                    </Link>
                  </p>
                </div>
                <Button
                  aria-label="הכללת העובדה"
                  className="shrink-0"
                  disabled={busy || fact.text == null}
                  onClick={() => onInclude(fact)}
                  size="compact"
                  variant="secondary"
                >
                  <Plus aria-hidden="true" className="size-icon-md" />
                  הכללה
                </Button>
              </li>
            ))}
          </ul>
          {selection.omitted.length <= OMITTED_PREVIEW ? null : (
            <Button
              className="self-start"
              onClick={() => setShowAllOmitted(!showAllOmitted)}
              size="compact"
              variant="ghost"
            >
              {showAllOmitted ? "הצגת פחות" : `הצגת כל ${selection.omitted.length} העובדות`}
            </Button>
          )}
        </div>
      )}
    </section>
  );
};
