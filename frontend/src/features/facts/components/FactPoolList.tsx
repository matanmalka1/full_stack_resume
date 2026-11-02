import { AlertTriangle } from "lucide-react";
import { createElement } from "react";
import { Link } from "react-router-dom";

import type { Fact } from "@/api/contracts";
import { cx } from "@/ui/cx";
import {
  factContextLine,
  factLabel,
  factSourceIcon,
  factSourceLabel,
  factStatusIcons,
  factStatusLabels,
  factStyleLabel,
} from "../model/factLabels";
import type { FactPoolEntry } from "../model/factPool";
import { FactStatusBadge } from "./FactStatusBadge";

const OutOfSyncMark = () => (
  <span
    aria-label="מצב העובדה אינו תואם למצב האחרון ביומן"
    className="relative inline-flex shrink-0 items-center text-cv-blocker"
    // The icon inside is aria-hidden; role="img" presents it as one image for assistive
    // tech, which `<img>` (a void element) cannot do.
    // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
    role="img"
  >
    <AlertTriangle aria-hidden="true" className="size-icon-md" />
  </span>
);

/* The status cell. A wide screen draws every status as its pill; a phone keeps the pill
   only for the state a reader has to act on - a fact waiting for confirmation - and draws
   the settled state as a mark, its word kept as the accessible name. */
const StatusCell = ({ fact }: { fact: Fact }) => {
  if (fact.status === "pending") {
    return <FactStatusBadge status={fact.status} />;
  }
  const Icon = factStatusIcons[fact.status];
  return (
    <>
      <span className="max-lg:hidden">
        <FactStatusBadge status={fact.status} />
      </span>
      <span
        aria-label={factStatusLabels[fact.status]}
        className="inline-flex text-cv-accent lg:hidden"
        // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
        role="img"
      >
        <Icon aria-hidden="true" className="size-5" />
      </span>
    </>
  );
};

/* Grouped by the knowledge file a fact lives in - the axis the chips above narrow by,
   and the one thing every fact in the pool has exactly one of. Groups keep the order the
   pool arrived in: the store's own order is what the store and the integrity report show. */
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

/* The pool is one table, drawn two ways, as the design draws it. A wide screen sees it as
   a table: a fact per row, its kind, origin and status in columns, the wording the row's
   link. A phone sees each knowledge file as a card of rows under a small heading - a tile
   naming the file, the wording with its origin under it, the status at the far end - and
   the whole row is the link. One tree rather than a list beside a table, so every fact
   has one link and one name; the group headings are rows of their own that only a phone
   shows, which is why each knowledge file is a `tbody`. */
export const FactPoolList = ({
  entries,
  factHref,
}: {
  entries: FactPoolEntry[];
  factHref: (factId: string) => string;
}) => (
  <div className="lg:overflow-x-auto lg:rounded-surface lg:border lg:border-cv-hairline lg:bg-cv-surface lg:shadow-surface">
    <table className="w-full border-collapse text-label max-lg:block lg:min-w-160">
      <caption className="sr-only">רשימת העובדות</caption>
      <thead className="max-lg:hidden">
        <tr className="bg-cv-canvas">
          {["עובדה", "סוג הצגה", "מקור", "מעמד"].map((heading) => (
            <th className="px-4.5 py-3 text-start text-caption font-bold text-cv-text-muted" key={heading} scope="col">
              {heading}
            </th>
          ))}
        </tr>
      </thead>
      {groupBySource(entries).map(({ entries: grouped, source }) => (
        <tbody className="max-lg:mb-3.5 max-lg:flex max-lg:flex-col max-lg:last:mb-0" key={source}>
          <tr className="lg:hidden">
            <th
              className="block pb-2 text-start text-support font-bold text-cv-text-muted"
              colSpan={4}
              dir="auto"
              scope="colgroup"
            >
              {factSourceLabel(source)}
            </th>
          </tr>
          {grouped.map(({ fact, outOfSync }, index) => {
            const context = factContextLine(fact);
            return (
              <tr
                className={cx(
                  "relative border-t border-cv-canvas",
                  "max-lg:flex max-lg:items-center max-lg:gap-3 max-lg:border-x max-lg:border-x-cv-hairline max-lg:bg-cv-surface max-lg:p-3.5 max-lg:transition-colors max-lg:hover:bg-cv-surface-muted",
                  index === 0 && "max-lg:rounded-t-surface max-lg:border-t-cv-hairline",
                  index === grouped.length - 1 &&
                    "max-lg:rounded-b-surface max-lg:border-b max-lg:border-b-cv-hairline",
                  fact.status === "pending" && "lg:bg-cv-canvas/60",
                )}
                key={fact.fact_id}
              >
                <td className="px-4.5 py-3 max-lg:flex max-lg:min-w-0 max-lg:flex-1 max-lg:items-center max-lg:gap-3 max-lg:p-0">
                  <span
                    aria-hidden="true"
                    className="flex size-9 shrink-0 items-center justify-center rounded-control-sm bg-cv-canvas text-cv-accent lg:hidden"
                  >
                    {createElement(factSourceIcon(fact.source), { className: "size-4.5" })}
                  </span>
                  <span className="min-w-0 max-lg:flex-1">
                    {/* On a phone the link's box stretches over the whole row. */}
                    <Link
                      className="font-bold text-cv-text max-lg:block max-lg:text-body max-lg:leading-snug max-lg:after:absolute max-lg:after:inset-0 lg:underline lg:underline-offset-2"
                      dir="auto"
                      to={factHref(fact.fact_id)}
                    >
                      {factLabel(fact)}
                    </Link>
                    {context === "" ? null : (
                      <span className="block truncate text-caption text-cv-text-muted lg:hidden" dir="auto">
                        {context}
                      </span>
                    )}
                  </span>
                  {outOfSync ? (
                    <span className="ms-2 inline-flex align-middle">
                      <OutOfSyncMark />
                    </span>
                  ) : null}
                </td>
                <td className="px-4.5 py-3 text-cv-text-muted max-lg:hidden">{factStyleLabel(fact.resume_style)}</td>
                <td className="max-w-60 truncate px-4.5 py-3 text-cv-text-muted max-lg:hidden" dir="auto">
                  {context === "" ? "—" : context}
                </td>
                <td className="px-4.5 py-3 max-lg:shrink-0 max-lg:p-0">
                  <StatusCell fact={fact} />
                </td>
              </tr>
            );
          })}
        </tbody>
      ))}
    </table>
  </div>
);
