import { Sparkles } from "lucide-react";
import type { Emphasis } from "@/api/contracts";
import { cx } from "@/ui/cx";
import { emphasisLabels } from "@/features/preparation";
import type { ContentSummary, SelectionSummary } from "../model/draftOverview";
import { claimOriginLabels } from "../model/draftLabels";
import type { EditableDocument } from "../model/drafts.types";

interface DraftContentSummaryProps {
  content: ContentSummary;
  draft: EditableDocument;
  selection: SelectionSummary;
}

/* How the content in front of the reader was produced.

   The draft is the result of two decisions, both the writer's: which facts it took from
   the Profile's pool for this role, and how each chosen fact became a line - as written,
   reworded for the role, or not backed at all. This says both in one place, above the
   lines they describe. Removing a line is the editor's, and stays in the outline. Every
   number is the document's own accounting; nothing is re-derived from the pool. */
export const DraftContentSummary = ({ content, draft, selection }: DraftContentSummaryProps) => {
  const emphasis = draft.content?.["emphasis"] as Emphasis;

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
          ה־AI בחר עובדות מהמאגר לפי ניתוח המשרה והדגש <span className="font-semibold">{emphasisLabels[emphasis]}</span>
          , ומהן נבנו השורות. כל שורה מסומנת לפי המקור שלה, ומתחת לכל שורה אפשר לראות את העובדה שממנה נבנתה.
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
      </p>
    </section>
  );
};
