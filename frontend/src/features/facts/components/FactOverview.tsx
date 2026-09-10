import { FileText, Tags } from "lucide-react";
import type { ReactNode } from "react";

import type { Fact } from "@/api/contracts";
import { factLabelInLanguage, factSourceLabel, factStyleLabel } from "../model/factLabels";
import { FactStatusBadge } from "./FactStatusBadge";

const DetailBlock = ({ children, label }: { children: ReactNode; label: string }) => (
  <div className="min-w-0 rounded-control bg-cv-surface-muted px-3.5 py-3">
    <p className="text-support font-medium text-cv-text-muted">{label}</p>
    <div className="mt-1 text-support leading-6 text-cv-text" dir="auto">
      {children}
    </div>
  </div>
);

export const FactOverview = ({ fact }: { fact: Fact }) => {
  /* Both renderings, English first: it is the one the CV is built from, and the Hebrew
     one reads as its companion rather than as a second title. Neither is rewritten to
     match the other - they are separate stored values and stay that way. */
  const english = factLabelInLanguage(fact, "en");
  const hebrew = fact.renderings.he === english ? undefined : fact.renderings.he;

  return (
    <section aria-labelledby="selected-fact-heading">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-cv-border pb-4">
        <div className="min-w-0 flex-1">
          <p className="mb-1.5 text-support font-semibold text-cv-accent">עובדת מועמד</p>
          <h2 className="text-heading-sm font-bold leading-7 text-cv-text" dir="auto" id="selected-fact-heading">
            {english}
          </h2>
          {hebrew === undefined ? null : (
            <p className="mt-1 text-support text-cv-text-muted" dir="rtl">
              {hebrew}
            </p>
          )}
        </div>
        <FactStatusBadge className="px-2.5 py-0.5" status={fact.status} />
      </div>

      <div className="mt-4">
        <DetailBlock label="משמעות עובדתית">{fact.meaning}</DetailBlock>
      </div>

      {/* Source and presentation type, and nothing else. The attestation and the canonical
          id used to sit here too: both are record-keeping rather than reading, the id is a
          string nobody reads off a screen, and the lifecycle history below already says
          how the fact got its status. Neither value changed - they are simply not what
          this panel is for. */}
      <dl className="mt-4 flex flex-wrap items-start gap-x-2.5 gap-y-1 border-y border-cv-border py-3">
        <FileText aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-cv-text-muted" />
        <dt className="text-support font-medium text-cv-text-muted">מקור וסוג</dt>
        <dd className="min-w-0 text-support text-cv-text">
          {factSourceLabel(fact.source)} · {factStyleLabel(fact.resume_style)}
        </dd>
      </dl>

      {fact.tags.length === 0 ? null : (
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          <Tags aria-hidden="true" className="me-0.5 size-4 text-cv-text-muted" />
          <span className="me-1 text-support font-medium text-cv-text-muted">תגיות</span>
          {fact.tags.map((tag) => (
            <span
              className="rounded-pill bg-cv-surface-sunken px-2.5 py-1 text-support text-cv-text-muted"
              dir="auto"
              key={tag}
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </section>
  );
};
