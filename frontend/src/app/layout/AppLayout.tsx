import { useQuery } from "@tanstack/react-query";
import { useLayoutEffect, useState } from "react";
import { Outlet } from "react-router-dom";

import { settingsQueryOptions } from "@/api/settings";
import { cx } from "@/ui/cx";
import { applyTheme, cacheTheme } from "./theme";
import { AppHeader } from "./AppHeader";
import { type DisplaySettings, DisplaySettingsPreviewProvider } from "@/features/settings";
import { RouteFocusManager } from "./RouteFocusManager";
import { useSidebarCollapse } from "./sidebar";
import { useInWorkflow } from "../workflowRoutes";

/* The frame every route renders inside: the masthead, the content column, and the two
   behaviors that belong to navigating rather than to any screen.

   The sidebar's width lives in this grid, not in the header, so the collapse state is
   held here and handed down: the column and its contents change together.

   Display density and text size are the reader's own settings and apply to the whole
   document, so they are set once here rather than by each screen. */
export const AppLayout = () => {
  const inWorkflow = useInWorkflow();
  const settings = useQuery(settingsQueryOptions).data?.settings;
  const [displayPreview, setDisplayPreview] = useState<DisplaySettings | null>(null);
  const displaySettings = displayPreview ?? settings;
  const sidebar = useSidebarCollapse();

  useLayoutEffect(() => {
    if (settings !== undefined) cacheTheme(settings.ui_theme);
    if (displaySettings !== undefined) applyTheme(displaySettings.ui_theme);
  }, [settings, displaySettings]);

  return (
    <div
      className={cx(
        "min-h-screen text-cv-text lg:grid",
        sidebar.collapsed ? "lg:grid-cols-[4.5rem_minmax(0,1fr)]" : "lg:grid-cols-[13rem_minmax(0,1fr)]",
      )}
      data-density={displaySettings?.ui_density ?? "comfortable"}
      data-route-density={inWorkflow ? "focus" : "work"}
      data-sidebar={sidebar.collapsed ? "collapsed" : "expanded"}
      data-text-size={displaySettings?.ui_text_size ?? "normal"}
    >
      <RouteFocusManager />
      <DisplaySettingsPreviewProvider onPreview={setDisplayPreview}>
        {/* Inside a wizard step a phone gives the whole screen to the step: its compact
            header carries the way back and its action bar the way on, so the masthead and
            the bottom navigation fold away below the large breakpoint. */}
        <AppHeader collapsed={sidebar.collapsed} hiddenOnPhone={inWorkflow} onToggleCollapsed={sidebar.toggle} />
        {/* The page's end clears the bottom navigation bar a narrow screen pins over it. */}
        <main className="page-gutter min-w-0 pt-5 pb-[calc(var(--cv-bottom-nav-height)+1.5rem)] sm:pt-6 lg:col-start-2 lg:row-start-1">
          <Outlet />
        </main>
      </DisplaySettingsPreviewProvider>
    </div>
  );
};
