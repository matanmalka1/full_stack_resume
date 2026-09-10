import { AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";

import { cx } from "@/ui/cx";
import type { FactPoolEntry } from "../model/factPool";
import { FactProvenance, FactTags, FactWording } from "./FactIdentity";
import { FactStatusBadge } from "./FactStatusBadge";

const defaultFactHref = (factId: string): string => `?fact=${encodeURIComponent(factId)}`;

const FactPoolRow = ({
  entry: { fact, outOfSync },
  selected,
  to,
}: {
  entry: FactPoolEntry;
  selected: boolean;
  to: string;
}) => (
  <li className={cx("p-4 transition-colors hover:bg-cv-surface-muted", selected && "bg-cv-accent-soft")}>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <Link aria-current={selected ? "true" : undefined} className="min-w-0 flex-1" to={to}>
        <FactWording fact={fact} />
      </Link>
      <div className="flex shrink-0 items-center gap-2">
        {outOfSync ? (
          <span
            aria-label="מצב העובדה אינו תואם למצב האחרון ביומן"
            className="inline-flex items-center gap-1 text-cv-blocker"
            // The icon inside is aria-hidden; role="img" presents the pair as one image
            // for assistive tech, which `<img>` (a void element) cannot do.
            // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
            role="img"
          >
            <AlertTriangle aria-hidden="true" className="size-4" />
          </span>
        ) : null}
        <FactStatusBadge className="px-2.5 py-0.5" status={fact.status} />
      </div>
    </div>

    <FactProvenance className="mt-3" fact={fact} />
    <FactTags className="mt-3" tags={fact.tags} />
  </li>
);

/* The stored facts as a scannable list: wording, then status, then where it came from.
   Read-only - every write to a fact happens through the lifecycle controls, never by
   editing a row here. */
export const FactPoolList = ({
  entries,
  factHref = defaultFactHref,
  selectedFactId,
}: {
  entries: FactPoolEntry[];
  factHref?: (factId: string) => string;
  selectedFactId?: string | null;
}) => (
  <ul
    aria-label="רשימת העובדות"
    className="max-h-[32rem] divide-y divide-cv-border overflow-y-auto rounded-control border border-cv-border"
  >
    {entries.map((entry) => (
      <FactPoolRow
        entry={entry}
        key={entry.fact.fact_id}
        selected={entry.fact.fact_id === selectedFactId}
        to={factHref(entry.fact.fact_id)}
      />
    ))}
  </ul>
);
