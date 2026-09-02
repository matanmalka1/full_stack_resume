import type { ReactNode } from "react";

import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

interface BackLinkProps {
  children: ReactNode;
  /* What the link is a way back to, for anyone who hears the landmark rather than
     seeing where it sits on the page. */
  label: string;
  to: string;
}

/* One step up, named. It replaced the two-tab switch that sat on Job Detail and on CV
   preparation: tabs make two screens read as two panels of one object, and these are a
   record and the work done against it - the job outlives every draft made from it, and
   preparation is entered from the job rather than shown beside it.

   A link, not a button: the browser's own open-in-new-tab, middle click, and history
   keep working, and Back still walks the way the reader came. */
export const BackLink = ({ children, label, to }: BackLinkProps) => (
  <nav aria-label={label}>
    <Link
      className="inline-flex min-h-11 items-center gap-1 rounded-control text-support font-semibold text-cv-text-muted transition-colors duration-200 hover:text-cv-text"
      to={to}
    >
      {/* The page is RTL, so back points right. */}
      <ChevronRight aria-hidden="true" className="size-4 shrink-0" />
      <span className="truncate">{children}</span>
    </Link>
  </nav>
);
