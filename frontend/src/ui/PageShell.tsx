import type { ReactNode } from "react";

import { Card } from "./Card";
import { PageHeading } from "./PageHeading";

/* A page is a card when it is a work surface - a draft, a form, one Application being
   worked on - because the card is what separates that work from the canvas behind it.
   A board is not: its rows already carry their own sheet, so a card around the whole
   route only nests one frame inside another and forces the table to break back out of
   the padding it was just given. Such a page declares `plain` and puts its own surface
   where the content actually is. */
type PageSurface = "card" | "plain";

interface PageShellProps {
  actions?: ReactNode;
  children?: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  navigation?: ReactNode;
  surface?: PageSurface;
  title: ReactNode;
}

/* Route pages share one document surface and one outer measure. Keeping the masthead,
   body rhythm, and width here makes every route align with the application header;
   components that need a shorter reading measure constrain their own text instead. */
export const PageShell = ({
  actions,
  children,
  description,
  eyebrow,
  navigation,
  surface = "card",
  title,
}: PageShellProps) => {
  const Surface = surface === "card" ? Card : "section";

  return (
    <Surface aria-labelledby="route-heading" className="page-frame">
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
    </Surface>
  );
};
