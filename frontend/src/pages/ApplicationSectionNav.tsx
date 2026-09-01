import { Link } from "react-router-dom";

import { cx } from "../ui/cx";
import { type ApplicationView, applicationViews } from "./ApplicationViews";

interface ApplicationSectionNavProps {
  value: ApplicationView;
}

/* These are two sections of one Application, not two panels of one object. Links keep
   native keyboard, open-in-new-tab, and middle-click behavior; `replace` preserves the
   existing history contract, where Back returns to the Application list rather than to
   the other section. */
export const ApplicationSectionNav = ({ value }: ApplicationSectionNavProps) => (
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
          replace
          to={{ search: option.value === "preparation" ? "" : "?view=tracking" }}
        >
          {option.label}
        </Link>
      ))}
    </div>
  </nav>
);
