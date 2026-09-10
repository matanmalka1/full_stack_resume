import { FileText, Fingerprint, Quote, Tags } from "lucide-react";
import type { ReactNode } from "react";

import type { Fact } from "@/api/contracts";
import { LtrText } from "@/ui/LtrText";
import { factLabel, factSourceLabel, factStyleLabels } from "../model/factLabels";
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
  const title = factLabel(fact);
  const english = fact.renderings.en === title ? null : fact.renderings.en;

  return (
    <section aria-labelledby="selected-fact-heading">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-cv-border pb-4">
        <div className="min-w-0 flex-1">
          <p className="mb-1.5 text-support font-semibold text-cv-accent">עובדת מועמד</p>
          <h2 className="text-heading-sm font-bold leading-7 text-cv-text" dir="auto" id="selected-fact-heading">
            {title}
          </h2>
        </div>
        <FactStatusBadge className="px-2.5 py-0.5" status={fact.status} />
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <DetailBlock label="משמעות עובדתית">{fact.meaning}</DetailBlock>
        {english === null ? null : <DetailBlock label="ניסוח באנגלית">{english}</DetailBlock>}
      </div>

      <dl className="mt-4 grid gap-3 border-y border-cv-border py-4 sm:grid-cols-2">
        <div className="flex min-w-0 items-start gap-2.5">
          <FileText aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-cv-text-muted" />
          <div className="min-w-0">
            <dt className="text-support font-medium text-cv-text-muted">מקור וסוג</dt>
            <dd className="mt-0.5 text-support text-cv-text">
              {factSourceLabel(fact.source)} · {factStyleLabels[fact.resume_style]}
            </dd>
          </div>
        </div>
        <div className="flex min-w-0 items-start gap-2.5">
          <Quote aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-cv-text-muted" />
          <div className="min-w-0">
            <dt className="text-support font-medium text-cv-text-muted">אסמכתה</dt>
            <dd className="mt-0.5 text-support text-cv-text" dir="auto">
              {fact.provenance}
            </dd>
          </div>
        </div>
        <div className="flex min-w-0 items-start gap-2.5 sm:col-span-2">
          <Fingerprint aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-cv-text-muted" />
          <div className="min-w-0">
            <dt className="text-support font-medium text-cv-text-muted">מזהה קנוני</dt>
            <dd className="mt-0.5 flex flex-wrap items-center gap-x-2 text-support text-cv-text">
              <LtrText mono>{fact.fact_id}</LtrText>
              <span aria-hidden="true" className="text-cv-text-muted">
                ·
              </span>
              <LtrText>{fact.source}</LtrText>
            </dd>
          </div>
        </div>
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
