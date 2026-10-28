import type { ReactNode } from "react";

import { cx } from "./cx";

export type EyebrowTone = "accent" | "blocker";

const eyebrowClasses: Record<EyebrowTone, string> = {
  accent: "text-cv-accent",
  blocker: "text-cv-blocker",
};

interface PageHeadingProps {
  children: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  eyebrowTone?: EyebrowTone;
  id: string;
}

/* A.2: focus moves to the page heading after a route change. The heading only marks
   itself with data-route-heading; moving focus is RouteFocusManager's, so that a
   heading mounting outside a navigation - the first screen of a visit - does not put a
   focus ring on a reader who never left anywhere. */
export const PageHeading = ({ children, description, eyebrow, eyebrowTone = "accent", id }: PageHeadingProps) => {
  return (
    <>
      {eyebrow === undefined ? null : (
        <p className={cx("mb-1 text-support font-bold tracking-wide", eyebrowClasses[eyebrowTone])}>{eyebrow}</p>
      )}
      {/* A.3: a heading is usually a Hebrew constant, but the route error boundary
          passes a backend title and detail through here, so each picks its own
          direction rather than inheriting the RTL shell. */}
      {/* The desktop design sets a route's title as the page's one display line - 30px,
          extrabold - over a 15px sub-line; a phone keeps the compact 22px heading its own
          design draws. */}
      <h1
        className="text-heading-md font-bold tracking-tight text-cv-text lg:text-heading-page lg:font-extrabold"
        data-route-heading
        dir="auto"
        id={id}
        tabIndex={-1}
      >
        {children}
      </h1>
      {description === undefined ? null : (
        <p className="mt-1 max-w-2xl text-support leading-6 text-cv-text-muted lg:text-body" dir="auto">
          {description}
        </p>
      )}
    </>
  );
};
