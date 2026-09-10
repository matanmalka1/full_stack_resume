import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Outlet } from "react-router-dom";

import { settingsQueryOptions } from "@/api/settings";
import { AppHeader } from "./AppHeader";
import { type DisplaySettings, DisplaySettingsPreviewProvider } from "./DisplaySettingsPreview";
import { RouteFocusManager } from "./RouteFocusManager";
import { useInWorkflow } from "../workflowRoutes";

/* The frame every route renders inside: the masthead, the content column, and the two
   behaviors that belong to navigating rather than to any screen.

   Display density and text size are the reader's own settings and apply to the whole
   document, so they are set once here rather than by each screen. */
export const AppLayout = () => {
  const inWorkflow = useInWorkflow();
  const settings = useQuery(settingsQueryOptions).data?.settings;
  const [displayPreview, setDisplayPreview] = useState<DisplaySettings | null>(null);
  const displaySettings = displayPreview ?? settings;

  return (
    <div
      className="min-h-screen text-cv-text lg:grid lg:grid-cols-[15rem_minmax(0,1fr)]"
      data-density={displaySettings?.ui_density ?? "comfortable"}
      data-route-density={inWorkflow ? "focus" : "work"}
      data-text-size={displaySettings?.ui_text_size ?? "normal"}
    >
      <RouteFocusManager />
      <AppHeader />

      <DisplaySettingsPreviewProvider onPreview={setDisplayPreview}>
        <main className="page-gutter min-w-0 py-5 sm:py-6 lg:col-start-2 lg:row-start-1">
          <Outlet />
        </main>
      </DisplaySettingsPreviewProvider>
    </div>
  );
};
