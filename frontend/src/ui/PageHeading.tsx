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
  /* Heading and description are kept for assistive tech but not drawn below the large
     breakpoint, where the top bar already names the screen (`PhoneTitle`); a description
     left standing without its heading would read as a stray line of body text. */
  hiddenOnPhone?: boolean;
  id: string;
}

/* A.2: focus moves to the page heading after a route change. The heading only marks
   itself with data-route-heading; moving focus is RouteFocusManager's, so that a
   heading mounting outside a navigation - the first screen of a visit - does not put a
   focus ring on a reader who never left anywhere. */
export const PageHeading = ({ children, description, eyebrow, eyebrowTone = "accent", hiddenOnPhone = false, id }: PageHeadingProps) => {
  return (
    <>
      {eyebrow === undefined ? null : (
        <p className={cx("mb-1 text-label font-bold", eyebrowClasses[eyebrowTone])}>{eyebrow}</p>
      )}
      {/* A.3: a heading is usually a Hebrew constant, but the route error boundary
          passes a backend title and detail through here, so each picks its own
          direction rather than inheriting the RTL shell. */}
      <h1
        className={cx(
          "text-title font-extrabold tracking-tight text-cv-text lg:text-display",
          hiddenOnPhone && "max-lg:sr-only",
        )}
        data-route-heading
        dir="auto"
        id={id}
        tabIndex={-1}
      >
        {children}
      </h1>
      {description === undefined ? null : (
        <p
          className={cx(
            "mt-1 max-w-2xl text-label text-cv-text-muted lg:mt-1.5 lg:text-body",
            hiddenOnPhone && "max-lg:sr-only",
          )}
          dir="auto"
        >
          {description}
        </p>
      )}
    </>
  );
};
