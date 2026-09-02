import { PlusCircle, ShieldCheck, Sparkles, UserCheck, Zap } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, type To } from "react-router-dom";

import { buttonClasses } from "../../ui/Button";
import { surfaceClasses } from "../../ui/Surface";

interface DashboardHeaderProps {
  newApplicationTo: To;
  onOpenQuickIntake: () => void;
  totalCount: number | undefined;
}

export const DashboardHeader = ({ newApplicationTo, onOpenQuickIntake, totalCount }: DashboardHeaderProps) => {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <header className={surfaceClasses("relative overflow-hidden bg-cv-surface p-5 shadow-surface sm:p-6")}>
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 left-0 w-80 bg-gradient-to-r from-cv-accent-soft/60 to-transparent"
      />

      <div className="relative z-10 flex flex-col items-start justify-between gap-5 lg:flex-row lg:items-center">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-pill border border-cv-accent/20 bg-cv-accent-soft px-2.5 py-0.5 text-support font-bold text-cv-accent">
              <Sparkles aria-hidden="true" className="size-3.5" />
              CV Engine
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-pill border border-cv-success/20 bg-cv-success-soft px-2.5 py-0.5 text-support font-bold text-cv-success">
              <ShieldCheck aria-hidden="true" className="size-3.5" />
              בדיקת עובדות לפני אישור
            </span>
          </div>

          <div>
            <h1
              className="text-heading-lg font-extrabold tracking-tight text-cv-text"
              data-route-heading
              id="route-heading"
              ref={headingRef}
              tabIndex={-1}
            >
              לוח מועמדויות ומעקב גיוס
            </h1>
            <p className="mt-1 max-w-3xl text-support text-cv-text-muted">
              ניהול תהליכי גיוס, התאמת קורות חיים לדרישות המשרה ובקרה על כל שלב בדרך להגשה.
            </p>
          </div>

          <div className="flex items-center gap-1.5 text-support font-medium text-cv-text-muted">
            <UserCheck aria-hidden="true" className="size-4 text-cv-accent" />
            {totalCount === undefined ? "טוען את מספר המועמדויות…" : `${totalCount} מועמדויות במערכת`}
          </div>
        </div>

        <div className="flex w-full shrink-0 flex-wrap items-center gap-2.5 sm:w-auto">
          <button
            className={buttonClasses("secondary", "flex-1 sm:flex-none")}
            onClick={onOpenQuickIntake}
            title="הזנה מהירה של פרטי משרה"
            type="button"
          >
            <Zap aria-hidden="true" className="size-4 text-cv-accent" />
            קליטה מהירה
          </button>
          <Link className={buttonClasses("primary", "flex-1 sm:flex-none")} to={newApplicationTo}>
            <PlusCircle aria-hidden="true" className="size-4" />
            קליטת משרה חדשה
          </Link>
        </div>
      </div>
    </header>
  );
};
