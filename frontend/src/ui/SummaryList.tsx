import type { ReactNode } from "react";

import { cx } from "./cx";
import { LtrText } from "./LtrText";

/* Summary rows accept arbitrary React nodes and therefore have no universal semantic id;
   their order is static within each rendered definition. */
/* oxlint-disable react/no-array-index-key */

export interface SummaryItem {
  /* Renders the value as an A.3 LTR island: version ids, ETags, filenames, timestamps. */
  ltr?: boolean;
  /* With `ltr`: set in the monospace face, for a hash or an identifier read character by
     character. */
  mono?: boolean;
  term: ReactNode;
  value: ReactNode;
}

interface SummaryListProps {
  className?: string;
  items: SummaryItem[];
}

export const SummaryList = ({ className, items }: SummaryListProps) => {
  return (
    /* The value column is sized to its content rather than to the page. As `1fr` it
       swallowed every spare column of a wide screen, so a short value - an id, a type,
       a timestamp - sat alone at the start of a band of empty space with its own term
       stranded at the far edge. `max-content` keeps the pair readable as a pair, and the
       trailing `1fr` spacer absorbs the remainder instead. */
    <dl className={cx("grid gap-x-6 gap-y-3 sm:grid-cols-[max-content_minmax(0,max-content)_1fr]", className)}>
      {items.map((item, index) => (
        <div className="contents" key={index}>
          <dt className="text-support font-medium text-cv-text-muted">{item.term}</dt>
          {/* An LTR island isolates itself; any other value may be Hebrew or backend
              English, so it picks its own direction - inside the cell, not as the cell. With
              `dir="auto"` on the `dd` itself an English company name made the whole cell
              LTR, so it hugged the far edge of its column while the Hebrew terms beside it
              sat on the near one. */}
          <dd className="text-support text-cv-text">
            {item.ltr === true ? (
              <LtrText mono={item.mono}>{item.value}</LtrText>
            ) : (
              <span dir="auto">{item.value}</span>
            )}
          </dd>
          <div aria-hidden="true" className="hidden sm:block" />
        </div>
      ))}
    </dl>
  );
};
