import { useQuery } from "@tanstack/react-query";
import { Settings } from "lucide-react";
import { Link, Outlet, useMatch, useMatches } from "react-router-dom";

import { RouteFocusManager } from "./app/RouteFocusManager";
import { WorkflowLandmark, WorkflowLandmarkSteps } from "./app/WorkflowLandmark";
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
      className="min-h-screen text-cv-text"
      data-density={settings?.ui_density ?? "comfortable"}
      data-text-size={settings?.ui_text_size ?? "normal"}
    >
      <RouteFocusManager />
      {/* The landmark wraps the header too, so the stage a page publishes can be shown
          on the header line rather than in a band of its own. */}
      <WorkflowLandmark>
        <header className="sticky top-0 z-30 border-b border-cv-border bg-cv-surface/85 backdrop-blur-xl">
          <div className="mx-auto flex min-h-16 max-w-[90rem] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2 sm:px-6 lg:px-8">
            {/* A wordmark rather than a logo tile: this is a local document tool, and
                the brass rule under the name does more to place it than a gradient
                square with a spark in it. */}
            <Link className="group shrink-0 rounded-control" to="/">
              <span className="block text-heading-sm font-extrabold tracking-tight text-cv-text">
                קורות חיים
              </span>
              <span className="block h-0.5 w-8 bg-cv-brass transition-all duration-200 group-hover:w-full" />
            </Link>

            <div className="order-3 w-full min-w-0 md:order-none md:w-auto">
              <WorkflowLandmarkSteps />
            </div>

            <div className="ms-auto flex min-w-0 items-center gap-3">
              {applicationContext === undefined ? null : (
                <div className="hidden min-w-0 border-e border-cv-border pe-3 text-end sm:block">
                  <p className="truncate text-support font-bold text-cv-text" dir="auto">
                    {applicationContext.company}
                  </p>
                  <p className="truncate text-support text-cv-text-muted" dir="auto">
                    {applicationContext.target_role}
                  </p>
                </div>
              )}
              <Link className={buttonClasses("ghost")} to="/settings">
                <Settings aria-hidden="true" className="size-4" />
                הגדרות
              </Link>
            </div>
          </div>
        </header>

        <main
          className={cx(
            "mx-auto w-full px-4 py-8 sm:px-6 sm:py-10 lg:px-8",
            isDraftEditor ? "max-w-[90rem]" : "max-w-5xl",
          )}
        >
          <Outlet />
        </main>
      </WorkflowLandmark>
    </div>
  );
};
