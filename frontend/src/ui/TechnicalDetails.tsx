import type { ReactNode } from "react";

import { cx } from "./cx";

interface TechnicalDetailsProps {
  children: ReactNode;
  className?: string;
  summary?: string;
}

/* A.2/A.5: technical codes and provenance stay collapsed. The safe backend detail is
   shown in the surrounding text; this only holds what is useful but not primary. */
export const TechnicalDetails = ({
  children,
  className,
  summary = "פרטים טכניים",
}: TechnicalDetailsProps) => {
  return (
    <details className={cx("text-support", className)}>
      <summary className="cursor-pointer rounded-control text-cv-text-muted">{summary}</summary>
      <div className="mt-2 leading-6 text-cv-text-muted">{children}</div>
    </details>
  );
};
