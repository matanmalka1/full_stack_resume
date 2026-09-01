import type { ReactNode } from "react";

import { cx } from "./cx";
import { LtrText } from "./LtrText";

export interface SummaryItem {
  /* Renders the value as an A.3 LTR island: version ids, ETags, filenames, timestamps. */
  ltr?: boolean;
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
              English, so it picks its own direction. */}
          <dd className="text-support text-cv-text" dir={item.ltr === true ? undefined : "auto"}>
            {item.ltr === true ? <LtrText>{item.value}</LtrText> : item.value}
          </dd>
          <div aria-hidden="true" className="hidden sm:block" />
        </div>
      ))}
    </dl>
  );
};
