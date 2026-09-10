import { AlertTriangle } from "lucide-react";

import type { FactPoolEntry } from "../model/factPool";
import { FactProvenance, FactTags, FactWording } from "./FactIdentity";
import { FactStatusBadge } from "./FactStatusBadge";

const FactPoolRow = ({ entry: { fact, outOfSync } }: { entry: FactPoolEntry }) => (
  <li className="p-4 transition-colors hover:bg-cv-surface-muted">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <FactWording className="min-w-0 flex-1" fact={fact} />
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
export const FactPoolList = ({ entries }: { entries: FactPoolEntry[] }) => (
  <ul
    aria-label="רשימת העובדות הקנוניות"
    className="max-h-[32rem] divide-y divide-cv-border overflow-y-auto rounded-control border border-cv-border"
  >
    {entries.map((entry) => (
      <FactPoolRow entry={entry} key={entry.fact.fact_id} />
    ))}
  </ul>
);
