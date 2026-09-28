import { useState } from "react";

import { Button } from "@/ui/Button";

const VISIBLE_KEYWORDS = 10;

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
