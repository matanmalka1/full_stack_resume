import { useState } from "react";

import { Button } from "@/ui/Button";

const VISIBLE_KEYWORDS = 10;

/* What the role is, in the analysis' own words, with the terms it picked out of the
   posting beneath it.

   The summary is the provider's short account of its reading and is not translated: a
   Hebrew rendering here would be this client paraphrasing a string it does not own. It
   leads the panel because it is what a reader checks first - "did it understand the
   job?" - before any count below it means anything. Keywords follow as a compact line
   rather than a section of their own; past the first few they add length, not meaning,
   so the rest wait behind one press. */
export const RoleSummary = ({ keywords, summary }: { keywords: string[]; summary: string | null }) => {
  const [allKeywords, setAllKeywords] = useState(false);
  if (summary === null && keywords.length === 0) {
    return null;
  }
  const shown = allKeywords ? keywords : keywords.slice(0, VISIBLE_KEYWORDS);
  const hidden = keywords.length - shown.length;

  return (
    <section aria-labelledby="role-summary-heading" className="flex flex-col gap-3">
      <h3 className="text-body font-semibold text-cv-text" id="role-summary-heading">
        מה המשרה מחפשת
      </h3>
      {summary === null ? null : (
        <p className="text-body leading-7 text-cv-text" dir="auto">
          {summary}
        </p>
      )}
      {keywords.length === 0 ? null : (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="me-1 text-caption font-semibold text-cv-text-muted">מילות מפתח:</span>
          {/* Output, not a control: a flat tinted ground, visibly not the bordered pill the
              list filters use for things you can select. */}
          {shown.map((keyword) => (
            <span
              className="rounded-control bg-cv-surface-muted px-2 py-0.5 text-caption text-cv-text-muted"
              dir="auto"
              key={keyword}
            >
              {keyword}
            </span>
          ))}
          {keywords.length > VISIBLE_KEYWORDS ? (
            <Button onClick={() => setAllKeywords((value) => !value)} variant="ghost">
              {allKeywords ? "פחות" : `עוד ${hidden}`}
            </Button>
          ) : null}
        </div>
      )}
    </section>
  );
};
