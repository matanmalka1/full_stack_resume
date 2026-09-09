import type { ReactNode } from "react";

import { PageHeading, type EyebrowTone } from "./PageHeading";
import { cx } from "./cx";

interface PageShellProps {
  actions?: ReactNode;
  children?: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  eyebrowTone?: EyebrowTone;
  /* Where the page sits in a longer piece of work, drawn above the masthead. The shell
     knows of no such progression, so the page supplies one where it has one and nothing
     where it does not. */
  landmark?: ReactNode;
  /* "wide" is the shared outer measure, which suits listings and record views. "form"
     is a shorter reading measure for a page whose whole body is one column of inputs:
     a text field stretched across the full frame is harder to scan, not easier.

     "wizard" is one step of a guided flow. It is narrower than "wide" because a step asks
     one thing: spread across the board's 110rem the same content became a wall of panels
     with room for several of them abreast, which is what a dashboard looks like and not
     what a step does. The draft editor keeps "wide" - it is the one step whose content is
     a document beside the evidence for each of its lines, and a split of two readable
     columns needs the room. */
  measure?: "wide" | "wizard" | "form";
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
  eyebrowTone,
  landmark,
  measure = "wide",
  navigation,
  title,
}: PageShellProps) => {
  return (
    <section
      aria-labelledby="route-heading"
      className={cx(
        "page-frame",
        measure === "form" ? "[--page-measure:48rem]" : undefined,
        measure === "wizard" ? "[--page-measure:64rem]" : undefined,
      )}
    >
      {navigation === undefined ? null : <div className="mb-5">{navigation}</div>}
      {landmark === undefined ? null : <div className="mb-5">{landmark}</div>}
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 border-b border-cv-border pb-2">
        <div className="min-w-0">
          <PageHeading description={description} eyebrow={eyebrow} eyebrowTone={eyebrowTone} id="route-heading">
            {title}
          </PageHeading>
        </div>
        {actions}
      </div>
      {children === undefined ? null : <div className="mt-6 flex flex-col gap-6">{children}</div>}
    </section>
  );
};
