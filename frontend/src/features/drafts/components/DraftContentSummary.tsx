import { Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

import { routePaths } from "@/app/routePaths";
import { cx } from "@/ui/cx";
import { emphasisLabels, factSelectionAnchor } from "@/features/preparation";
import type { ContentSummary, SelectionSummary } from "../model/draftOverview";
import { claimOriginLabels } from "../model/draftLabels";
import type { EditableDocument } from "../model/drafts.types";

interface DraftContentSummaryProps {
  applicationId: string;
  content: ContentSummary;
  draft: EditableDocument;
  selection: SelectionSummary;
}

/* How the content in front of the reader was produced.

   The draft is the result of two decisions: which facts the selection took from the
   knowledge base for this role, and how each chosen fact became a line - as written,
   reworded for the role, or not backed at all. This says both in one place, above the
   lines they describe. It reports the selection and does not edit it: the selection has
   one screen, the analysis step, where each fact is shown against the requirements it
   answers and both include and exclude are offered together with the AI proposal. A
   second, narrower editor here disagreed with that one on what a change was and when it
   was saved. Removing a line is still the editor's, and stays in the outline. Every
   number is the document's own accounting; nothing is re-derived from the pool. */
export const DraftContentSummary = ({ applicationId, content, draft, selection }: DraftContentSummaryProps) => {
  const emphasis = draft.selection.emphasis_override ?? draft.selection.emphasis;

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
        {" · "}
        <Link
          className="font-semibold text-cv-accent hover:text-cv-accent-hover"
          to={`${routePaths.application(applicationId)}#${factSelectionAnchor}`}
        >
          שינוי בחירת העובדות
        </Link>
      </p>
    </section>
  );
};
