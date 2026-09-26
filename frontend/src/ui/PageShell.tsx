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
  /* A block rendered after the masthead and `children`, at the section's own full
     measure. The landmark sits above the masthead rather than in a column beside it, so
     nothing is inset any more; this remains the place a step renders what must come
     after its body - the analysis step's two-column row and the commit bar after it. `children` still
     renders in the usual place; this is an addition, not a replacement. */
  afterBody?: ReactNode;
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
  title: ReactNode;
}

/* Route pages share one plain outer measure. Keeping the masthead, body rhythm, and
   width here makes every route align with the application header; components that need
   a surface or a shorter reading measure provide it around their own content. */
export const PageShell = ({
  actions,
  afterBody,
  children,
  description,
  eyebrow,
  eyebrowTone,
  landmark,
  measure = "wide",
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
      <div>
        {landmark === undefined ? null : <aside className="mb-5">{landmark}</aside>}
        <div className="min-w-0">
          <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2 border-b border-cv-hairline pb-2">
            <div className="min-w-0">
              <PageHeading description={description} eyebrow={eyebrow} eyebrowTone={eyebrowTone} id="route-heading">
                {title}
              </PageHeading>
            </div>
            {actions}
          </div>
          {children === undefined ? null : (
            <div className="mt-section-gap flex flex-col gap-section-gap">{children}</div>
          )}
        </div>
      </div>
      {afterBody === undefined ? null : <div className="mt-section-gap">{afterBody}</div>}
    </section>
  );
};
