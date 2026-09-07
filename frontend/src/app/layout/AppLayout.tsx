import { useQuery } from "@tanstack/react-query";
import { Outlet } from "react-router-dom";

import { settingsQueryOptions } from "@/api/settings";
import { AppHeader } from "./AppHeader";
import { RouteFocusManager } from "./RouteFocusManager";

/* The frame every route renders inside: the masthead, the content column, and the two
   behaviors that belong to navigating rather than to any screen.

   Display density and text size are the reader's own settings and apply to the whole
   document, so they are set once here rather than by each screen. */
export const AppLayout = () => {
  const settings = useQuery(settingsQueryOptions).data?.settings;

  return (
    <div
      className="min-h-screen text-cv-text"
      data-density={settings?.ui_density ?? "comfortable"}
      data-text-size={settings?.ui_text_size ?? "normal"}
    >
      <RouteFocusManager />
      <AppHeader />

      <main className="w-full px-4 py-5 sm:px-6 sm:py-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
};
