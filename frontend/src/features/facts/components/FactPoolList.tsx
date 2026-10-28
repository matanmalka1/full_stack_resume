import { AlertTriangle } from "lucide-react";
import { createElement } from "react";
import { Link } from "react-router-dom";

import type { FactStatus } from "@/api/contracts";
import { cx } from "@/ui/cx";
import { toneTextClasses } from "@/ui/tone";
import {
  factLabelInLanguage,
  factSourceIcon,
  factSourceLabel,
  factStyleLabel,
  factStatusIcons,
  factStatusLabels,
  factStatusTones,
} from "../model/factLabels";
import type { FactPoolEntry } from "../model/factPool";

/* The widths of the wide screen's table columns after the wording, shared by the header
   and every row so the two line up. The status column's width sits on the status mark. */
const columnClasses = { source: "w-44 shrink-0", style: "w-36 shrink-0" };

const defaultFactHref = (factId: string): string => `?fact=${encodeURIComponent(factId)}`;

/* The status as a mark rather than a pill or a word. Every value a row used to restate -
   the source file, the tags, the status word - is spelled out in full on the fact itself
   beside the list, so repeating it ninety-eight times bought nothing and cost the wording
   most of its width. What is left in the row is the fact and one icon: which lifecycle
   state it is in is what decides whether the row is even usable yet, and an icon carries
   that without taking a line. Its Hebrew word stays as the accessible name.

   A phone's row is narrow, and the one state a reader there has to act on - a fact waiting
   for confirmation - is drawn as its word in a pill at the row's far end; the settled state
   keeps its icon there. A wide screen's row is a table row with a status column, so there
   every state is its word in a pill: the dark one waits, the quiet one is settled. */
const FactRowStatus = ({ status }: { status: FactStatus }) => {
  const Icon = factStatusIcons[status];
  const pill = status === "pending";

  return (
    <span
      aria-label={factStatusLabels[status]}
      className={cx(
        "mt-0.5 inline-flex shrink-0 order-last max-lg:self-center lg:mt-0 lg:w-32",
        toneTextClasses[factStatusTones[status]],
      )}
      // The icon inside is aria-hidden; role="img" presents the pair as one image for
      // assistive tech, which `<img>` (a void element) cannot do.
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      role="img"
    >
      <Icon aria-hidden="true" className={cx("size-icon-md lg:hidden", pill && "max-lg:hidden")} />
      <span
        aria-hidden="true"
        className={cx(
          "rounded-pill px-2.5 py-1 text-caption font-bold whitespace-nowrap lg:py-0.5",
          pill ? "bg-cv-accent text-cv-on-accent" : "bg-cv-surface-sunken text-cv-text max-lg:hidden",
        )}
      >
        {factStatusLabels[status]}
      </span>
    </span>
  );
};

/* The icon is a module-level component chosen by lookup, not one created here. */
const FactSourceTile = ({ source }: { source: string }) => (
  <span
    aria-hidden="true"
    className="flex size-9 shrink-0 items-center justify-center rounded-control bg-cv-surface-muted text-cv-text lg:hidden"
  >
    {createElement(factSourceIcon(source), { className: "size-icon-md" })}
  </span>
);

/* A row is an index entry, not a second copy of the fact: its wording, and the marks that
   say whether it is usable. Everything else - id, source, attestation, tags - is one click
   away and drawn in full there.

   The whole row is the link rather than the wording alone: a 4px target in a list of
   ninety-eight is a miss waiting to happen, and the row has nothing else to click.
   Selection is an accent fill plus a bar on the reader's side of the row, so the open
   fact is identifiable by shape as well as by colour. A phone shows the list and the fact
   one at a time, so there nothing beside the list is open and the row drops the mark;
   it leads with a tile naming the fact's knowledge file instead.

   A wide screen draws the same row as a line of a table: the wording, then its
   presentation type, its knowledge file and its status, each in a column under the
   header `FactPoolList` draws. The extra cells are part of the one row - not a second
   rendering of it - and are not drawn on a phone, where the group heading names the file
   and the record names the type. */
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
          "flex items-start gap-2.5 border-s-4 max-lg:items-center max-lg:gap-3 px-3 py-2.5 transition-colors max-lg:min-h-11 max-lg:border-s-0 max-lg:py-3 lg:items-center lg:gap-4 lg:px-4.5 lg:py-3.5",
          selected
            ? "border-s-cv-accent bg-cv-accent-soft max-lg:bg-transparent"
            : "border-s-transparent hover:bg-cv-surface-muted",
        )}
        to={to}
      >
        <FactSourceTile source={fact.source} />
        <FactRowStatus status={fact.status} />
        {/* English leads. It is the rendering the CV is built from, so it is the wording a
          person is actually choosing between here; the Hebrew rendering follows in the
          supporting size as a reading aid, and only when the store holds one distinct
          from what is already shown. `text-right` anchors both lines to the row's RTL
          edge (the shell is always RTL): with `dir="auto"` alone an English title sat
          left above a Hebrew line on the right, so every row zig-zagged. The bidi order
          inside each line is unchanged. */}
        <div className="min-w-0 flex-1">
          <p
            className="font-semibold text-cv-text text-right lg:font-bold lg:underline lg:decoration-cv-border-strong lg:underline-offset-4"
            dir="auto"
          >
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
        <span className={cx(columnClasses.style, "text-support text-cv-text-muted max-lg:hidden")}>
          {factStyleLabel(fact.resume_style)}
        </span>
        <span className={cx(columnClasses.source, "text-support text-cv-text-muted max-lg:hidden")} dir="auto">
          {factSourceLabel(fact.source)}
        </span>
      </Link>
    </li>
  );
};

/* Grouped by the knowledge file a fact lives in - the same axis the source chips narrow
   by, and the one thing every fact in the pool has exactly one of. On a phone the page
   scrolls (a box inside a scrolling page traps the thumb), and each group is a rounded
   card under a plain label that states the file once per group instead of once per row.

   A wide screen draws the pool as one table on the page. Each group opens with a header
   row across the table naming the file and how many facts it holds, and it sticks to the
   top of the page while its rows scroll by, so the count per file reads there as on a
   phone. The file also has its own column, for a row read on its own.

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
    className="max-h-[70dvh] min-h-64 overflow-y-auto rounded-control border border-cv-border max-lg:max-h-none max-lg:min-h-0 max-lg:overflow-visible max-lg:border-0 lg:max-h-none lg:min-h-0 lg:overflow-clip lg:rounded-surface lg:bg-cv-surface lg:shadow-surface"
    dir="ltr"
    // A named region rather than one long list: the groups below carry the lists.
    // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
    role="group"
  >
    <div className="max-lg:flex max-lg:flex-col max-lg:gap-4 lg:divide-y lg:divide-cv-border" dir="rtl">
      {/* The table's column header. The row's own link already reads each value in turn,
          so the header is drawn for the eye only. */}
      <div
        aria-hidden="true"
        className="flex items-center gap-4 border-s-4 border-s-transparent bg-cv-surface-sunken px-4.5 py-3 text-caption font-bold text-cv-text-muted max-lg:hidden"
      >
        <span className="min-w-0 flex-1">עובדה</span>
        <span className={columnClasses.style}>סוג הצגה</span>
        <span className={columnClasses.source}>מקור</span>
        <span className="w-32 shrink-0">מעמד</span>
      </div>
      {groupBySource(entries).map(({ entries: grouped, source }) => (
        <section key={source}>
          <h3 className="lg:bg-cv-surface-muted lg:px-4.5 lg:py-2 sticky top-0 z-(--cv-z-content-raised) flex items-baseline justify-between gap-control-gap border-b border-cv-border bg-cv-surface-sunken px-3 py-1.5 text-support font-semibold text-cv-text-muted max-lg:static max-lg:border-0 max-lg:bg-transparent max-lg:px-1 max-lg:pt-0 max-lg:font-bold">
            <span dir="auto">{factSourceLabel(source)}</span>
            <span className="font-normal">{grouped.length}</span>
          </h3>
          <ul className="divide-y divide-cv-border max-lg:overflow-hidden max-lg:rounded-surface max-lg:border max-lg:border-cv-border max-lg:bg-cv-surface">
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
  </div>
);
