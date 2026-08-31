import { Link } from "react-router-dom";

import { cx } from "../ui/cx";

/* The two views of one Application, and the only way between them.

   The header above already names the company and the role, so this is not a second
   breadcrumb: it is the switch between the Application's two independent axes - what the
   document is doing and what the recruiter is doing. Both keep the same context, so
   neither is a level below the other and neither is reached by a back gesture.

   It is a pair of links rather than a tab contract: each view is a route with its own URL,
   reloadable and bookmarkable, and the panels below are not tab panels. The current one is
   still a link's worth of markup, but it points nowhere - `aria-current` says which of the
   two the reader is on. */
const views = [
  { key: "preparation", label: "הכנת קורות החיים", path: "" },
  { key: "tracking", label: "מעקב גיוס", path: "/tracking" },
] as const;

export type ApplicationView = (typeof views)[number]["key"];

export const ApplicationViews = ({
  applicationId,
  current,
}: {
  applicationId: string;
  current: ApplicationView;
}) => (
  <nav aria-label="תצוגות המועמדות" className="mt-4 flex gap-1 border-b border-cv-border">
    {views.map((view) => {
      const active = view.key === current;

      return (
        <Link
          aria-current={active ? "page" : undefined}
          className={cx(
            "-mb-px inline-flex min-h-11 items-center border-b-2 px-4 py-2 text-support font-semibold transition-colors duration-200",
            active
              ? "border-cv-accent text-cv-accent"
              : "border-transparent text-cv-text-muted hover:border-cv-border-strong hover:text-cv-text",
          )}
          key={view.key}
          to={`/applications/${encodeURIComponent(applicationId)}${view.path}`}
        >
          {view.label}
        </Link>
      );
    })}
  </nav>
);
