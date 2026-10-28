import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link, type To } from "react-router-dom";

import { buttonClasses } from "./Button";
import { PageHeading, type EyebrowTone } from "./PageHeading";
import { cx } from "./cx";

/* One step of the trail above a record's heading. The last step is the page itself and
   takes no `to`; every step before it is a link back up the trail. */
export interface PageShellCrumb {
  label: ReactNode;
  /* Router state carried by the link, e.g. the board's return state. */
  state?: unknown;
  to?: To;
}

interface PageShellProps {
  /* The page's commands, on the heading row's inline-end edge. On desktop they centre on
     the title block rather than hanging from its top line, as the design draws them. */
  actions?: ReactNode;
  /* A bordered chevron on the heading row's start edge, leading back to the page this
     one was opened from. `label` is its accessible name - "חזרה לפרטי המועמדות", not
     "חזרה". Desktop only: below the large breakpoint a page that has a way back draws it
     in its own compact header (`WizardStepShell`'s phone header, the record views'
     back bar), and a second chevron there would be a duplicate. */
  back?: { label: string; state?: unknown; to: To };
  /* The trail from a top-level area to this record, drawn above the heading row:
     "לוח המועמדויות / מפתח/ת Backend". Top-level areas reached from the navigation pass
     none - the navigation already says where the reader is. Desktop only, for the same
     reason as `back`. */
  breadcrumb?: readonly PageShellCrumb[];
  children?: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  eyebrowTone?: EyebrowTone;
  /* Where the page sits in a longer piece of work, drawn above the masthead. The shell
     knows of no such progression, so the page supplies one where it has one and nothing
     where it does not. */
  landmark?: ReactNode;
  /* Where the landmark stands from the large breakpoint. "below-masthead" puts it between
     the heading row and the body, as the desktop workflow draws its stage strip under the
     step's title; below the breakpoint it stays above the masthead either way. */
  landmarkPlacement?: "above" | "below-masthead";
  /* A mark beside the title naming the record - the company's initial on an application.
     Decorative: the title says it. Desktop only, like `back`. */
  leading?: ReactNode;
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
  /* How the masthead row stands below the large breakpoint. "hidden" keeps it in the
     document for assistive tech - the route heading the shell focuses must exist - but
     gives a record opened from a list the whole screen. "centered" centres it, for a page
     that is nothing but a statement and its way out. */
  phoneMasthead?: "visible" | "hidden" | "centered";
  /* `phoneMasthead`'s counterpart from the large breakpoint. "hidden" keeps the heading in
     the document for assistive tech but gives the body the page - a record chosen by the
     URL (the fact detail) replaces its list's masthead with its own trail at every width. */
  wideMasthead?: "visible" | "hidden";
  title: ReactNode;
}

/* Route pages share one plain outer measure. Keeping the masthead, body rhythm, and
   width here makes every route align with the application header; components that need
   a surface or a shorter reading measure provide it around their own content. */
export const PageShell = ({
  actions,
  afterBody,
  back,
  breadcrumb,
  children,
  description,
  eyebrow,
  eyebrowTone,
  landmark,
  landmarkPlacement = "above",
  leading,
  measure = "wide",
  phoneMasthead = "visible",
  title,
  wideMasthead = "visible",
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
      {/* With the landmark below the masthead, the column is laid out by `order` from the
          large breakpoint rather than rendered twice: one tree keeps every name unique. The
          landmark stays first in the reading order, as it is on a phone. */}
      <div className={cx(landmarkPlacement === "below-masthead" && "lg:flex lg:flex-col")}>
        {landmark === undefined ? null : (
          <aside
            className={cx(
              "mb-5 max-lg:mb-3",
              landmarkPlacement === "below-masthead" && "lg:order-3 lg:mt-section-gap lg:mb-0",
            )}
          >
            {landmark}
          </aside>
        )}
        {breadcrumb === undefined || breadcrumb.length === 0 ? null : (
          <nav aria-label="מיקום" className="mb-5 max-lg:hidden lg:order-1">
            <ol className="flex flex-wrap items-center gap-1.5 text-support text-cv-text-muted">
              {breadcrumb.map((crumb, index) => (
                // The trail is a fixed path for the page, never reordered, so its position is its identity.
                // oxlint-disable-next-line react/no-array-index-key
                <li className="flex items-center gap-1.5" key={index}>
                  {index === 0 ? null : <span aria-hidden="true">/</span>}
                  {crumb.to === undefined ? (
                    <span aria-current={index === breadcrumb.length - 1 ? "page" : undefined} dir="auto">
                      {crumb.label}
                    </span>
                  ) : (
                    <Link
                      className="underline underline-offset-2 hover:text-cv-text"
                      dir="auto"
                      state={crumb.state}
                      to={crumb.to}
                    >
                      {crumb.label}
                    </Link>
                  )}
                </li>
              ))}
            </ol>
          </nav>
        )}
        <div className={cx("min-w-0", landmarkPlacement === "below-masthead" && "lg:contents")}>
          {/* The heading stands on the canvas without a rule under it at every width: the
              design separates the masthead from the body by space alone. */}
          <div
            className={cx(
              "flex flex-wrap items-start justify-between gap-x-6 gap-y-2 lg:order-2 lg:items-center",
              phoneMasthead === "hidden" && "max-lg:sr-only",
              phoneMasthead === "centered" && "max-lg:justify-center max-lg:text-center",
              wideMasthead === "hidden" && "lg:sr-only",
            )}
          >
            <div className="flex min-w-0 items-center gap-4 max-lg:contents">
              {back === undefined ? null : (
                <Link
                  aria-label={back.label}
                  className={buttonClasses("secondary", "shrink-0 max-lg:hidden", "icon-md")}
                  state={back.state}
                  to={back.to}
                >
                  <ChevronRight aria-hidden="true" className="size-icon-lg" />
                </Link>
              )}
              {leading === undefined ? null : (
                <div aria-hidden="true" className="shrink-0 max-lg:hidden">
                  {leading}
                </div>
              )}
              <div className="min-w-0">
                <PageHeading description={description} eyebrow={eyebrow} eyebrowTone={eyebrowTone} id="route-heading">
                  {title}
                </PageHeading>
              </div>
            </div>
            {actions}
          </div>
          {children === undefined ? null : (
            <div className="mt-section-gap flex flex-col gap-section-gap lg:order-4">{children}</div>
          )}
        </div>
      </div>
      {afterBody === undefined ? null : <div className="mt-section-gap">{afterBody}</div>}
    </section>
  );
};
