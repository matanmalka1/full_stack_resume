import type { ReactNode } from "react";

import { PageHeading } from "./PageHeading";

interface PageShellProps {
  actions?: ReactNode;
  children?: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
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
  navigation,
  title,
}: PageShellProps) => {
  return (
    <section aria-labelledby="route-heading" className="page-frame">
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
