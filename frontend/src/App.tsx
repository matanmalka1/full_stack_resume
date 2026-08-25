import { useQuery } from "@tanstack/react-query";
import { Settings, Sparkles } from "lucide-react";
import { Link, Outlet, useMatch, useMatches } from "react-router-dom";

import { RouteFocusManager } from "./app/RouteFocusManager";
import { WorkflowLandmark } from "./app/WorkflowLandmark";
import { applicationDetailQueryOptions } from "./api/applications";
import { settingsQueryOptions } from "./api/settings";
import { buttonClasses } from "./ui/Button";
import { cx } from "./ui/cx";

export const App = () => {
  const settings = useQuery(settingsQueryOptions).data?.settings;
  const isDraftEditor = useMatch("/applications/:applicationId/draft") !== null;
  const applicationId =
    useMatches()
      .map((match) => match.params.applicationId)
      .find((id) => id !== undefined) ?? null;
  const applicationContext = useQuery({
    ...applicationDetailQueryOptions(applicationId ?? ""),
    enabled: applicationId !== null,
  }).data?.application;

  return (
    <div
      className="min-h-screen bg-cv-canvas text-cv-text"
      data-density={settings?.ui_density ?? "comfortable"}
      data-text-size={settings?.ui_text_size ?? "normal"}
    >
      <RouteFocusManager />
      <header className="sticky top-0 z-30 border-b border-cv-border bg-cv-surface/90 backdrop-blur-xl">
        <div className="mx-auto flex min-h-18 max-w-[90rem] items-center justify-between gap-6 px-4 sm:px-6 lg:px-8">
          <Link className="group flex items-center gap-3 rounded-control" to="/">
            <span className="flex size-10 items-center justify-center rounded-surface bg-linear-to-br from-cv-accent to-cv-brand-deep text-cv-on-accent shadow-floating transition-transform duration-200 group-hover:-translate-y-0.5">
              <Sparkles aria-hidden="true" className="size-5" />
            </span>
            <span className="flex flex-col">
              <span className="text-heading-sm font-bold tracking-tight text-cv-text">
                סביבת קורות החיים
              </span>
              <span className="hidden text-support text-cv-text-muted sm:inline">Workspace מקומי ומאובטח</span>
            </span>
          </Link>
          {applicationContext === undefined ? null : (
            <div className="hidden min-w-0 flex-1 items-center justify-center lg:flex">
              <div className="min-w-0 rounded-pill border border-cv-border bg-cv-surface-muted px-4 py-2 text-center shadow-inner">
                <p className="truncate text-support font-bold text-cv-text" dir="auto">
                  {applicationContext.company}
                </p>
                <p className="truncate text-support text-cv-text-muted" dir="auto">
                  {applicationContext.target_role}
                </p>
              </div>
            </div>
          )}
          <Link className={buttonClasses("secondary")} to="/settings">
            <Settings aria-hidden="true" className="size-4" />
            הגדרות
          </Link>
        </div>
      </header>

      {/* The landmark reads the stage the current screen published from its projection
          rather than a constant the shell keeps. */}
      <WorkflowLandmark>
        <main
          className={cx(
            "mx-auto w-full px-4 py-8 sm:px-6 sm:py-10 lg:px-8",
            isDraftEditor ? "max-w-[90rem]" : "max-w-6xl",
          )}
        >
          <Outlet />
        </main>
      </WorkflowLandmark>
    </div>
  );
};
