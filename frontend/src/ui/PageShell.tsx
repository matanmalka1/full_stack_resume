import type { ReactNode } from "react";

import { Card } from "./Card";
import { PageHeading } from "./PageHeading";
import { cx } from "./cx";

export type PageWidth = "reading" | "editor" | "list";

const widthClasses: Record<PageWidth, string> = {
  reading: "max-w-5xl",
  editor: "max-w-[90rem]",
  list: "max-w-[110rem]",
};

interface PageShellProps {
  actions?: ReactNode;
  children?: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  title: ReactNode;
  width?: PageWidth;
}

/* Route pages share one document surface. Keeping the masthead border and body rhythm
   here means a page declares its content and measure without rebuilding the frame or
   teaching the application shell which route happens to need which width. */
export const PageShell = ({
  actions,
  children,
  description,
  eyebrow,
  title,
  width = "reading",
}: PageShellProps) => {
  return (
    <Card aria-labelledby="route-heading" className={cx("mx-auto w-full", widthClasses[width])}>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b border-cv-border pb-5">
        <div className="min-w-0">
          <PageHeading description={description} eyebrow={eyebrow} id="route-heading">
            {title}
          </PageHeading>
        </div>
        {actions}
      </div>
      {children === undefined ? null : <div className="mt-6 flex flex-col gap-6">{children}</div>}
    </Card>
  );
};
