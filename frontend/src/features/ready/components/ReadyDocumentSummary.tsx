import { Calendar, FileText, Languages, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { languageLabels } from "@/features/preparation";
import { formatDateTime } from "@/utils/formatDateTime";

const Fact = ({ icon: Icon, term, value }: { icon: LucideIcon; term: string; value: ReactNode }) => (
  /* On a phone a line of its own, its icon standing for the term; on a wide
     screen a small tile of its own, the term spelled out over the value. */
  <div className="flex items-center gap-2 lg:block lg:rounded-control lg:border lg:border-cv-hairline lg:bg-cv-surface lg:p-3">
    <Icon aria-hidden="true" className="size-icon-lg shrink-0 text-cv-text lg:hidden" />
    <dt className="sr-only lg:not-sr-only lg:text-caption lg:text-cv-text-muted">{term}</dt>
    <dd className="text-label lg:mt-0.5 lg:font-bold">{value}</dd>
  </div>
);

/* The finished file at a glance: its format and length, its language and the day it
   was issued - what the Ready read already says about it. The page count is the
   render's own measure, read beside it; absent, the format stands alone. */
export const ReadyFileFacts = ({
  approvedAt,
  language,
  pages,
}: {
  approvedAt: string | null;
  language: string;
  pages: number | null;
}) => {
  const languageName = language in languageLabels ? languageLabels[language as keyof typeof languageLabels] : language;

  return (
    <dl className="flex min-w-0 flex-1 flex-col justify-center gap-2.5 text-cv-text lg:grid lg:grid-cols-3 lg:gap-2">
      <Fact
        icon={FileText}
        term="קובץ"
        value={
          <>
            <span className="font-bold">PDF</span>
            {pages === null ? null : ` · ${pages === 1 ? "עמוד אחד" : `${pages} עמודים`}`}
          </>
        }
      />
      <Fact icon={Languages} term="שפה" value={languageName} />
      {approvedAt === null ? null : (
        <Fact
          icon={Calendar}
          term="הופק"
          value={
            <>
              <span className="lg:hidden">הופק ב־</span>
              {formatDateTime(approvedAt, "date")}
            </>
          }
        />
      )}
    </dl>
  );
};
