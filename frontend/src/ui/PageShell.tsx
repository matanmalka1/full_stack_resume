import type { ReactNode } from "react";

import { PageHeading } from "./PageHeading";
import { cx } from "./cx";

interface PageShellProps {
  actions?: ReactNode;
  children?: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  /* "wide" is the shared outer measure, which suits listings and record views. "form"
     is a shorter reading measure for a page whose whole body is one column of inputs:
     a text field stretched across the full frame is harder to scan, not easier. */
  measure?: "wide" | "form";
  navigation?: ReactNode;
  title: ReactNode;
}

/* Route pages share one plain outer measure. Keeping the masthead, body rhythm, and
   width here makes every route align with the application header; components that need
   a surface or a shorter reading measure provide it around their own content. */
export const PageShell = ({
  actions,
  children,
  description,
  eyebrow,
  measure = "wide",
  navigation,
  title,
}: PageShellProps) => {
  return (
    <section
      aria-labelledby="route-heading"
      className={cx("page-frame", measure === "form" ? "[--page-measure:48rem]" : undefined)}
    >
      {navigation === undefined ? null : <div className="mb-5">{navigation}</div>}
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 border-b border-cv-border pb-2">
        <div className="min-w-0">
          <PageHeading description={description} eyebrow={eyebrow} id="route-heading">
            {title}
          </PageHeading>
        </div>
        {actions}
      </div>
      {children === undefined ? null : <div className="mt-6 flex flex-col gap-6">{children}</div>}
    </section>
  );
};
