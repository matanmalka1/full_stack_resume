import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";

import type { FactStatus } from "@/api/contracts";
import { cx } from "@/ui/cx";
import {
  factLabelInLanguage,
  factSourceLabel,
  factStatusIcons,
  factStatusLabels,
  factStatusTones,
} from "../model/factLabels";
import type { FactPoolEntry } from "../model/factPool";

const defaultFactHref = (factId: string): string => `?fact=${encodeURIComponent(factId)}`;

/* The status as a mark rather than a pill or a word. Every value a row used to restate -
   the source file, the tags, the status word - is spelled out in full on the fact itself
   beside the list, so repeating it ninety-eight times bought nothing and cost the wording
   most of its width. What is left in the row is the fact and one icon: which lifecycle
   state it is in is what decides whether the row is even usable yet, and an icon carries
   that without taking a line. Its Hebrew word stays as the accessible name. */
const statusToneClasses = {
  success: "text-cv-success",
  warning: "text-cv-warning",
  blocker: "text-cv-blocker",
  progress: "text-cv-accent",
  neutral: "text-cv-text-muted",
} as const;

const FactRowStatus = ({ status }: { status: FactStatus }) => {
  const Icon = factStatusIcons[status];

  return (
    <span
      aria-label={factStatusLabels[status]}
      className={cx("mt-0.5 inline-flex shrink-0", statusToneClasses[factStatusTones[status]])}
      // The icon inside is aria-hidden; role="img" presents the pair as one image for
      // assistive tech, which `<img>` (a void element) cannot do.
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      role="img"
    >
      <Icon aria-hidden="true" className="size-icon-md" />
    </span>
  );
};

/* A row is an index entry, not a second copy of the fact: its wording, and the marks that
   say whether it is usable. Everything else - id, source, attestation, tags - is one click
   away and drawn in full there.

   The whole row is the link rather than the wording alone: a 4px target in a list of
   ninety-eight is a miss waiting to happen, and the row has nothing else to click.
   Selection is an accent fill plus a bar on the reader's side of the row, so the open
   fact is identifiable by shape as well as by colour. */
const FactPoolRow = ({
  entry: { fact, outOfSync },
  selected,
  to,
}: {
  entry: FactPoolEntry;
  selected: boolean;
  to: string;
}) => {
  const english = factLabelInLanguage(fact, "en");
  const hebrew = fact.renderings.he === english ? undefined : fact.renderings.he;

  return (
    <li>
      <Link
        aria-current={selected ? "true" : undefined}
        className={cx(
          "flex items-start gap-2.5 border-s-4 px-3 py-2.5 transition-colors",
          selected ? "border-s-cv-accent bg-cv-accent-soft" : "border-s-transparent hover:bg-cv-surface-muted",
        )}
        to={to}
      >
        <FactRowStatus status={fact.status} />
        {/* English leads. It is the rendering the CV is built from, so it is the wording a
          person is actually choosing between here; the Hebrew rendering follows in the
          supporting size as a reading aid, and only when the store holds one distinct
          from what is already shown. */}
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-cv-text" dir="auto">
            {english}
          </p>
          {hebrew === undefined ? null : (
            <p className="mt-0.5 text-support text-cv-text-muted" dir="rtl">
              {hebrew}
            </p>
          )}
        </div>
        {outOfSync ? (
          <span
            aria-label="מצב העובדה אינו תואם למצב האחרון ביומן"
            className="mt-0.5 inline-flex shrink-0 items-center text-cv-blocker"
            // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
            role="img"
          >
            <AlertTriangle aria-hidden="true" className="size-icon-md" />
          </span>
        ) : null}
      </Link>
    </li>
  );
};

/* Grouped by the knowledge file a fact lives in - the same axis the "מאגר מקור" filter
   narrows by, and the one thing every fact in the pool has exactly one of. As a heading
   above its facts it is stated once per group instead of once per row, and the group
   headings double as position while scrolling: they stick to the top of the scroll area,
   so it always says which store the rows under the cursor belong to.

   Groups keep the order the pool arrived in rather than being sorted here: the store's
   own order is what the store itself and the integrity report show. */
const groupBySource = (entries: FactPoolEntry[]): { entries: FactPoolEntry[]; source: string }[] => {
  const groups = new Map<string, FactPoolEntry[]>();

  for (const entry of entries) {
    const existing = groups.get(entry.fact.source);

    if (existing === undefined) {
      groups.set(entry.fact.source, [entry]);
    } else {
      existing.push(entry);
    }
  }

  return [...groups].map(([source, grouped]) => ({ entries: grouped, source }));
};

export const FactPoolList = ({
  entries,
  factHref = defaultFactHref,
  selectedFactId,
}: {
  entries: FactPoolEntry[];
  factHref?: (factId: string) => string;
  selectedFactId?: string | null;
}) => (
  <div
    aria-label="רשימת העובדות"
    className="max-h-[70dvh] min-h-64 overflow-y-auto rounded-control border border-cv-border lg:max-h-[calc(100dvh-9rem)]"
    // A named region rather than one long list: the groups below carry the lists.
    // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
    role="group"
  >
    {groupBySource(entries).map(({ entries: grouped, source }) => (
      <section key={source}>
        <h3 className="sticky top-0 z-(--cv-z-content-raised) flex items-baseline justify-between gap-control-gap border-b border-cv-border bg-cv-surface-sunken px-3 py-1.5 text-support font-semibold text-cv-text-muted">
          <span dir="auto">{factSourceLabel(source)}</span>
          <span className="font-normal">{grouped.length}</span>
        </h3>
        <ul className="divide-y divide-cv-border">
          {grouped.map((entry) => (
            <FactPoolRow
              entry={entry}
              key={entry.fact.fact_id}
              selected={entry.fact.fact_id === selectedFactId}
              to={factHref(entry.fact.fact_id)}
            />
          ))}
        </ul>
      </section>
    ))}
  </div>
);
