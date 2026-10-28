import { Download } from "lucide-react";

import type { ApplicationDetail } from "@/api/contracts";
import { documentPdfHref } from "@/api/documents";
import { fitLevelLabel } from "@/features/preparation";
import { buttonClasses } from "@/ui/Button";
import { formatDateTime } from "@/utils/formatDateTime";
import { isApplicationClosed } from "../model/applicationListItem";

/* The latest send of any version of the CV, from the recruitment history the projection
   already carries. */
const lastSubmittedAt = (detail: ApplicationDetail): string | null =>
  detail.recruitment_timeline.reduce<string | null>(
    (latest, item) =>
      item.item_type === "submission" && (latest === null || item.occurred_at > latest) ? item.occurred_at : latest,
    null,
  );

/* The wide screen's aside, under the reminder: the record at a glance - its fit, whether
   it is still open, when the CV was last sent - and the finished PDF.

   A phone has none of it here: the board's details sheet says the same facts there, and
   the Ready screen holds the file. On a wide screen the aside has the room, and a reader
   checking one application should not have to leave it to see them. The download is the
   document's own PDF, offered only while the projection says it is Ready - the server
   refuses it otherwise - and drawn disabled before that, so the place it will be is
   already known. */
export const ApplicationFacts = ({ detail }: { detail: ApplicationDetail }) => {
  const fit = detail.application.fit_level;
  const submittedAt = lastSubmittedAt(detail);
  const documentHash = detail.document_hash ?? null;
  const downloadable = detail.preparation_state === "ready" && documentHash !== null;

  return (
    <div className="flex flex-col gap-3 max-lg:hidden">
      <dl
        aria-label="המועמדות במבט"
        className="divide-y divide-cv-border rounded-surface border border-cv-border bg-cv-surface text-support shadow-surface"
      >
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <dt className="text-cv-text-muted">ציון התאמה</dt>
          <dd className="font-bold text-cv-text">{fit == null ? "טרם נותחה" : fitLevelLabel(fit)}</dd>
        </div>
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <dt className="text-cv-text-muted">סטטוס משרה</dt>
          <dd className="font-bold text-cv-text">{isApplicationClosed(detail) ? "סגורה" : "פתוחה"}</dd>
        </div>
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <dt className="text-cv-text-muted">הגשה</dt>
          <dd className="font-bold text-cv-text">
            {submittedAt === null ? "טרם נרשמה" : formatDateTime(submittedAt, "date")}
          </dd>
        </div>
      </dl>
      {downloadable ? (
        <a className={buttonClasses("secondary", "w-full")} href={documentPdfHref(detail.application.id, documentHash)}>
          <Download aria-hidden="true" className="size-icon-md" />
          הורדת PDF
        </a>
      ) : (
        <button className={buttonClasses("secondary", "w-full")} disabled type="button">
          <Download aria-hidden="true" className="size-icon-md" />
          הורדת PDF
          <span className="sr-only"> (זמינה כשקורות החיים מוכנים)</span>
        </button>
      )}
    </div>
  );
};
