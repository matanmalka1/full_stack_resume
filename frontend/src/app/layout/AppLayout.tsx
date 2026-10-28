import { useQuery } from "@tanstack/react-query";
import { useLayoutEffect, useState } from "react";
import { Outlet } from "react-router-dom";

import { settingsQueryOptions } from "@/api/settings";
import { cx } from "@/ui/cx";
import { applyTheme, cacheTheme } from "./theme";
import { AppHeader } from "./AppHeader";
import { type DisplaySettings, DisplaySettingsPreviewProvider } from "@/features/settings";
import { RouteFocusManager } from "./RouteFocusManager";
import { useInWorkflow } from "../workflowRoutes";

/* The frame every route renders inside: the sidebar (a top bar and a bottom tab bar on
   a phone), the content column, and the two behaviors that belong to navigating rather
   than to any screen.

   Display density and text size are the reader's own settings and apply to the whole
   document, so they are set once here rather than by each screen. */
export const AppLayout = () => {
  const inWorkflow = useInWorkflow();
  const settings = useQuery(settingsQueryOptions).data?.settings;
  const [displayPreview, setDisplayPreview] = useState<DisplaySettings | null>(null);
  const displaySettings = displayPreview ?? settings;

  useLayoutEffect(() => {
    if (settings !== undefined) cacheTheme(settings.ui_theme);
    if (displaySettings !== undefined) applyTheme(displaySettings.ui_theme);
  }, [settings, displaySettings]);

  return (
    <div
      className="min-h-screen text-cv-text lg:grid lg:grid-cols-[15.5rem_minmax(0,1fr)]"
      data-density={displaySettings?.ui_density ?? "comfortable"}
      data-route-density={inWorkflow ? "focus" : "work"}
      data-text-size={displaySettings?.ui_text_size ?? "normal"}
    >
      <RouteFocusManager />
      <DisplaySettingsPreviewProvider onPreview={setDisplayPreview}>
        {/* Inside a wizard step a phone gives the whole screen to the step: its compact
            header carries the way back and its action bar the way on, so the masthead and
            the bottom navigation fold away below the large breakpoint. */}
        <AppHeader hiddenOnPhone={inWorkflow} />
        {/* The page's end clears the bottom navigation bar a narrow screen pins over it.
            On a phone the top bar's own bottom padding is most of the space above the
            heading; a wizard step, which has no top bar, starts from the screen's edge. */}
        <main
          className={cx(
            "page-gutter min-w-0 pb-[calc(var(--cv-bottom-nav-height)+1.5rem)] lg:col-start-2 lg:row-start-1 lg:pt-8 lg:pb-10",
            inWorkflow ? "pt-4" : "pt-2",
          )}
        >
          <Outlet />
        </main>
      </DisplaySettingsPreviewProvider>
    </div>
  );
};
