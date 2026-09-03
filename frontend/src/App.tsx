import { useQuery } from "@tanstack/react-query";
import { Settings } from "lucide-react";
import { Link, Outlet } from "react-router-dom";

import { RouteFocusManager } from "./app/RouteFocusManager";
import { WorkflowLandmark, WorkflowLandmarkSteps } from "./app/WorkflowLandmark";
import { appRoutes } from "./app/appRoutes";
import { settingsQueryOptions } from "./api/settings";
import { buttonClasses } from "./ui/Button";

export const App = () => {
  const settings = useQuery(settingsQueryOptions).data?.settings;

  return (
    <div
      className="min-h-screen text-cv-text"
      data-density={settings?.ui_density ?? "comfortable"}
      data-text-size={settings?.ui_text_size ?? "normal"}
    >
      <RouteFocusManager />
      <WorkflowLandmark>
        <header className="sticky top-0 z-30 border-b border-cv-border bg-cv-surface/85 backdrop-blur-xl">
          <div className="page-frame flex min-h-16 flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2 sm:px-6 lg:px-8">
            {/* A wordmark rather than a logo tile: this is a local document tool, and
                the accent rule under the name does more to place it than a gradient
                square with a spark in it. */}
            <Link className="group shrink-0 rounded-control" to={appRoutes.home}>
              <span className="block text-heading-sm font-extrabold tracking-tight text-cv-text">קורות חיים</span>
              <span className="block h-0.5 w-8 bg-cv-accent transition-all duration-200 group-hover:w-full" />
            </Link>

            <div className="ms-auto flex min-w-0 items-center gap-3">
              <Link className={buttonClasses("ghost")} to={appRoutes.settings}>
                <Settings aria-hidden="true" className="size-4" />
                הגדרות
              </Link>
            </div>
          </div>
        </header>

        <main className="w-full px-4 py-5 sm:px-6 sm:py-6 lg:px-8">
          <div className="page-frame mb-3 empty:hidden sm:mb-4">
            <WorkflowLandmarkSteps />
          </div>
          <Outlet />
        </main>
      </WorkflowLandmark>
    </div>
  );
};
