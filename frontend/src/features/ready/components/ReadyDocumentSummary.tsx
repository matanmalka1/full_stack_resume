import { Calendar, FileText, Languages, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { languageLabels } from "@/features/preparation";
import { cx } from "@/ui/cx";
import { formatDateTime } from "@/utils/formatDateTime";

/* The sketch is a fixed drawing: its bars never reorder, so their place is their key. */
/* oxlint-disable react/no-array-index-key */

/* The bars of a CV's first page, top to bottom: a name, a line under it, then three
   sections of a heading over its lines. Widths are shares of the page's width. */
const SKETCH = [
  { kind: "name", width: "w-3/5" },
  { kind: "subtitle", width: "w-2/5" },
  { kind: "gap" },
  { kind: "heading", width: "w-1/3" },
  { kind: "line", width: "w-full" },
  { kind: "line", width: "w-11/12" },
  { kind: "line", width: "w-full" },
  { kind: "gap" },
  { kind: "heading", width: "w-1/3" },
  { kind: "line", width: "w-full" },
  { kind: "line", width: "w-5/6" },
  { kind: "line", width: "w-11/12" },
  { kind: "line", width: "w-2/3" },
  { kind: "gap" },
  { kind: "heading", width: "w-1/3" },
  { kind: "line", width: "w-full" },
  { kind: "line", width: "w-4/5" },
] as const;

const barClasses = {
  name: "bg-cv-accent",
  subtitle: "bg-cv-border-strong",
  heading: "bg-cv-text-muted",
  line: "bg-cv-border",
} as const;

/* The finished file drawn as a page, not a preview of it: the rendered PDF is a download,
   not something this read can show, so the page is a schematic of where its parts sit.
   Decorative - the facts beside it are the information.

   "small" is the phone's thumbnail beside those facts; "large" the wide screen's page,
   A4 in proportion, standing in the column at the start of the screen. */
export const ReadyPageSketch = ({ className, size }: { className?: string; size: "small" | "large" }) => {
  const large = size === "large";
  return (
    <div
      aria-hidden="true"
      className={cx(
        "flex shrink-0 flex-col border border-cv-border bg-cv-surface",
        large
          ? "aspect-[210/297] w-full gap-2.5 rounded-item px-10 py-11 shadow-document"
          : "h-46.5 w-33 gap-1.5 rounded-control-sm px-3 py-3.5 shadow-floating",
        className,
      )}
    >
      {SKETCH.map((bar, index) =>
        bar.kind === "gap" ? (
          <span className={large ? "h-2" : "h-1"} key={index} />
        ) : (
          <span
            className={cx(
              "rounded-sm",
              bar.width,
              barClasses[bar.kind],
              large
                ? bar.kind === "name"
                  ? "h-4"
                  : bar.kind === "heading"
                    ? "h-2.25"
                    : bar.kind === "subtitle"
                      ? "h-2"
                      : "h-1.5"
                : bar.kind === "name"
                  ? "h-2"
                  : bar.kind === "heading"
                    ? "h-1.25"
                    : bar.kind === "subtitle"
                      ? "h-1"
                      : "h-0.75",
            )}
            key={index}
          />
        ),
      )}
    </div>
  );
};

const Fact = ({ icon: Icon, term, value }: { icon: LucideIcon; term: string; value: ReactNode }) => (
  /* On a phone a line beside the thumbnail, its icon standing for the term; on a wide
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
