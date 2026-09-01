import { Link } from "react-router-dom";

import { cx } from "../ui/cx";
import { type ApplicationView, applicationViews } from "./ApplicationViews";

interface ApplicationSectionNavProps {
  applicationId: string;
  value: ApplicationView;
}

/* These are two sections of one Application, not two panels of one object. Links keep
   native keyboard, open-in-new-tab, and middle-click behavior, and each move is a history
   entry: a tab that Back does not return from is a tab the reader cannot undo pressing.
   Back from here now walks the sections visited and reaches the list behind them, rather
   than skipping straight out of the Application. */
export const ApplicationSectionNav = ({ applicationId, value }: ApplicationSectionNavProps) => (
  <nav aria-label="תחומי המועמדות">
    <div className="inline-flex gap-1 rounded-surface border border-cv-border bg-cv-surface-muted p-1 shadow-inner">
      {applicationViews.map((option) => (
        <Link
          aria-current={option.value === value ? "page" : undefined}
          className={cx(
            "flex min-h-11 items-center rounded-control px-4 text-support font-semibold transition-all duration-200",
            option.value === value
              ? "bg-cv-surface text-cv-accent shadow-surface"
              : "text-cv-text-muted hover:bg-cv-surface-muted",
          )}
          key={option.value}
          to={
            option.value === "details"
              ? `/applications/${encodeURIComponent(applicationId)}`
              : `/applications/${encodeURIComponent(applicationId)}/preparation`
          }
        >
          {option.label}
        </Link>
      ))}
    </div>
  </nav>
);
