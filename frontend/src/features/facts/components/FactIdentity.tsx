import { Tags } from "lucide-react";

import type { Fact } from "@/api/contracts";
import { cx } from "@/ui/cx";
import { LtrText } from "@/ui/LtrText";
import { type SummaryItem, SummaryList } from "@/ui/SummaryList";
import { factLabel } from "../model/factLabels";

/* How a fact reads: its own wording first, the English rendering under it only when that
   is not already what is shown. The two are separate values in the store and stay
   separate here - neither is rewritten to stand in for the other. */
export const FactWording = ({ className, fact }: { className?: string; fact: Fact }) => {
  const label = factLabel(fact);
  const english = fact.renderings.en === label ? undefined : fact.renderings.en;

  return (
    <div className={className}>
      <p className="font-semibold text-cv-text" dir="auto">
        {label}
      </p>
      {english === undefined ? null : (
        <p className="mt-1 text-support text-cv-text-muted" dir="ltr">
          {english}
        </p>
      )}
    </div>
  );
};

/* Where the fact came from: its identity in the store, the knowledge file holding it,
   and the attestation that established it. Provenance is the reason a fact is allowed
   into a CV at all, so it is shown outright rather than behind a disclosure. */
export const FactProvenance = ({ className, fact }: { className?: string; fact: Fact }) => {
  const items: SummaryItem[] = [
    {
      term: "מזהה ומקור",
      value: (
        <span className="flex flex-wrap items-center gap-x-2">
          <LtrText mono>{fact.fact_id}</LtrText>
          <span aria-hidden="true">·</span>
          <LtrText>{fact.source}</LtrText>
        </span>
      ),
    },
    { term: "אסמכתה", value: fact.provenance },
  ];

  return <SummaryList className={className} items={items} />;
};

export const FactTags = ({ className, tags }: { className?: string; tags: string[] }) =>
  tags.length === 0 ? null : (
    <p className={cx("flex flex-wrap items-center gap-1.5 text-support text-cv-text-muted", className)}>
      <Tags aria-hidden="true" className="size-3.5" />
      {tags.map((tag) => (
        <span className="rounded-pill bg-cv-surface-sunken px-2 py-0.5" dir="auto" key={tag}>
          {tag}
        </span>
      ))}
    </p>
  );
