import { useQuery } from "@tanstack/react-query";
import { Link, Outlet } from "react-router-dom";

import { RouteFocusManager } from "./app/RouteFocusManager";
import { WorkflowLandmark } from "./app/WorkflowLandmark";
import { settingsQueryOptions } from "./api/settings";
import { buttonClasses } from "./ui/Button";

export const App = () => {
  const settings = useQuery(settingsQueryOptions).data?.settings;
  return (
    <div
      className="min-h-screen bg-cv-canvas text-cv-text"
      data-density={settings?.ui_density ?? "comfortable"}
      data-text-size={settings?.ui_text_size ?? "normal"}
    >
      <RouteFocusManager />
      <header className="border-b border-cv-border bg-cv-surface">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-6 px-6">
          <Link className="rounded-control text-heading-sm font-semibold text-cv-text" to="/">
            סביבת קורות החיים
          </Link>
          <Link className={buttonClasses("secondary")} to="/settings">
            הגדרות
          </Link>
        </div>
      </header>

      {/* The landmark reads the stage the current screen published from its projection
          rather than a constant the shell keeps. */}
      <WorkflowLandmark>
        <main className="mx-auto max-w-5xl px-6 py-12">
          <Outlet />
        </main>
      </WorkflowLandmark>
    </div>
  );
};
