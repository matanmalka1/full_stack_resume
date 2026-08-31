import { type ReactNode, useEffect, useRef } from "react";

import { cx } from "./cx";

type EyebrowTone = "accent" | "blocker";

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

/* A.2: focus moves to the page heading after a route change. The heading carries
   data-route-heading for RouteFocusManager and also claims focus when it mounts
   outside a navigation, such as inside the route error boundary. */
export const PageHeading = ({
  children,
  description,
  eyebrow,
  eyebrowTone = "accent",
  id,
}: PageHeadingProps) => {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <>
      {eyebrow === undefined ? null : (
        <p className={cx("mb-2 text-support font-bold tracking-wide", eyebrowClasses[eyebrowTone])}>
          {eyebrow}
        </p>
      )}
      {/* A.3: a heading is usually a Hebrew constant, but the route error boundary
          passes a backend title and detail through here, so each picks its own
          direction rather than inheriting the RTL shell. */}
      <h1
        className="text-heading-lg font-bold tracking-tight text-cv-text"
        data-route-heading
        dir="auto"
        id={id}
        ref={headingRef}
        tabIndex={-1}
      >
        {children}
      </h1>
      {description === undefined ? null : (
        <p className="mt-2 max-w-2xl text-body leading-7 text-cv-text-muted" dir="auto">
          {description}
        </p>
      )}
    </>
  );
};
