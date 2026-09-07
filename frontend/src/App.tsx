import { useQuery } from "@tanstack/react-query";
import { Outlet } from "react-router-dom";

import { GlobalHeader } from "./app/GlobalHeader";
import { RouteFocusManager } from "./app/RouteFocusManager";
import { WorkflowLandmark } from "./app/WorkflowLandmark";
import { settingsQueryOptions } from "./api/settings";

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
        <GlobalHeader />

        <main className="w-full px-4 py-5 sm:px-6 sm:py-6 lg:px-8">
          <Outlet />
        </main>
      </WorkflowLandmark>
    </div>
  );
};
