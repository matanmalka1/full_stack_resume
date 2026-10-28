import { Calendar, FileText, Languages } from "lucide-react";

import { languageLabels } from "@/features/preparation";
import { formatDateTime } from "@/utils/formatDateTime";

/* The finished file at a glance: a page drawn in outline beside what the Ready read
   already says about it - its format, its language and the day it was issued.

   The page is a schematic, not a preview. The rendered PDF is a download, not something
   this read can show, and a page count is not on it either, so the card names only what
   is known rather than a number it would have to guess.

   On a wide screen the page is the screen's large preview, drawn at a page's size, and
   the three facts sit under it as tiles, each naming itself. */
/* A phone's row is an icon beside the value, the term for assistive tech only; a wide
   screen's tile names the term over the value and drops the icon. */
const tileClasses =
  "flex items-center gap-2.5 lg:flex-col lg:items-start lg:gap-1 lg:rounded-surface lg:border lg:border-cv-border lg:bg-cv-surface lg:px-4 lg:py-3";
const termClasses = "sr-only lg:not-sr-only lg:text-caption lg:text-cv-text-muted";
const iconClasses = "size-icon-lg shrink-0 text-cv-text-muted lg:hidden";

export const ReadyDocumentSummary = ({ approvedAt, language }: { approvedAt: string | null; language: string }) => {
  const languageName = language in languageLabels ? languageLabels[language as keyof typeof languageLabels] : language;

  return (
    <div className="flex items-center gap-5 lg:flex-col lg:items-stretch lg:gap-4">
      {/* Lines in the shape of a CV's first page: a name, a rule, two sections. */}
      <div
        aria-hidden="true"
        className="flex aspect-[1/1.3] w-32 shrink-0 flex-col gap-1.5 rounded-control border border-cv-border bg-cv-surface p-3 shadow-surface sm:w-36 lg:w-full lg:gap-3 lg:rounded-none lg:p-12 lg:shadow-floating"
      >
        <span className="h-1.5 w-3/4 rounded-pill bg-cv-text lg:h-3.5" />
        <span className="h-1 w-1/2 rounded-pill bg-cv-border-strong lg:h-1.5" />
        <span className="mt-2 h-1 w-1/3 rounded-pill bg-cv-text-muted lg:mt-6 lg:h-2" />
        <span className="h-1 w-full rounded-pill bg-cv-border lg:h-1.5" />
        <span className="h-1 w-5/6 rounded-pill bg-cv-border lg:h-1.5" />
        <span className="h-1 w-4/6 rounded-pill bg-cv-border lg:h-1.5" />
        <span className="mt-2 h-1 w-1/3 rounded-pill bg-cv-text-muted lg:mt-6 lg:h-2" />
        <span className="h-1 w-full rounded-pill bg-cv-border lg:h-1.5" />
        <span className="h-1 w-3/4 rounded-pill bg-cv-border lg:h-1.5" />
      </div>
      <dl className="flex min-w-0 flex-1 flex-col gap-3 text-support text-cv-text lg:grid lg:grid-cols-3">
        <div className={tileClasses}>
          <dt className={termClasses}>סוג הקובץ</dt>
          <FileText aria-hidden="true" className={iconClasses} />
          <dd className="font-bold">PDF</dd>
        </div>
        <div className={tileClasses}>
          <dt className={termClasses}>שפת המסמך</dt>
          <Languages aria-hidden="true" className={iconClasses} />
          <dd className="lg:font-bold">{languageName}</dd>
        </div>
        {approvedAt === null ? null : (
          <div className={tileClasses}>
            <dt className={termClasses}>הופק</dt>
            <Calendar aria-hidden="true" className={iconClasses} />
            <dd className="lg:font-bold">
              <span className="lg:sr-only">הופק ב־</span>
              {formatDateTime(approvedAt, "date")}
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
};
