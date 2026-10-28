import { Calendar, FileText, Languages } from "lucide-react";

import { languageLabels } from "@/features/preparation";
import { formatDateTime } from "@/utils/formatDateTime";

/* The finished file at a glance: a page drawn in outline beside what the Ready read
   already says about it - its format, its language and the day it was issued.

   The page is a schematic, not a preview. The rendered PDF is a download, not something
   this read can show, and a page count is not on it either, so the card names only what
   is known rather than a number it would have to guess. */
export const ReadyDocumentSummary = ({ approvedAt, language }: { approvedAt: string | null; language: string }) => {
  const languageName = language in languageLabels ? languageLabels[language as keyof typeof languageLabels] : language;

  return (
    <div className="flex items-center gap-5">
      {/* Lines in the shape of a CV's first page: a name, a rule, two sections. */}
      <div
        aria-hidden="true"
        className="flex aspect-[1/1.3] w-32 shrink-0 flex-col gap-1.5 rounded-control border border-cv-border bg-cv-surface p-3 shadow-surface sm:w-36"
      >
        <span className="h-1.5 w-3/4 rounded-pill bg-cv-text" />
        <span className="h-1 w-1/2 rounded-pill bg-cv-border-strong" />
        <span className="mt-2 h-1 w-1/3 rounded-pill bg-cv-text-muted" />
        <span className="h-1 w-full rounded-pill bg-cv-border" />
        <span className="h-1 w-5/6 rounded-pill bg-cv-border" />
        <span className="h-1 w-4/6 rounded-pill bg-cv-border" />
        <span className="mt-2 h-1 w-1/3 rounded-pill bg-cv-text-muted" />
        <span className="h-1 w-full rounded-pill bg-cv-border" />
        <span className="h-1 w-3/4 rounded-pill bg-cv-border" />
      </div>
      <dl className="flex min-w-0 flex-1 flex-col gap-3 text-support text-cv-text">
        <div className="flex items-center gap-2.5">
          <dt className="sr-only">סוג הקובץ</dt>
          <FileText aria-hidden="true" className="size-icon-lg shrink-0 text-cv-text-muted" />
          <dd className="font-bold">PDF</dd>
        </div>
        <div className="flex items-center gap-2.5">
          <dt className="sr-only">שפת המסמך</dt>
          <Languages aria-hidden="true" className="size-icon-lg shrink-0 text-cv-text-muted" />
          <dd>{languageName}</dd>
        </div>
        {approvedAt === null ? null : (
          <div className="flex items-center gap-2.5">
            <dt className="sr-only">הופק</dt>
            <Calendar aria-hidden="true" className="size-icon-lg shrink-0 text-cv-text-muted" />
            <dd>הופק ב־{formatDateTime(approvedAt, "date")}</dd>
          </div>
        )}
      </dl>
    </div>
  );
};
