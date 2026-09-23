import { useIsFetching } from "@tanstack/react-query";
import { PanelRightClose, PanelRightOpen, Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { buttonClasses } from "@/ui/Button";
import { cx } from "@/ui/cx";
import { Tooltip } from "@/ui/Tooltip";
import { GlobalSearch } from "../search/GlobalSearch";
import { boardPath } from "../boardReturn";
import { routePaths } from "../routePaths";
import { AppNavigation } from "./AppNavigation";
import { ThemeToggle } from "./ThemeToggle";

/* Whether the application is currently talking to the server, anywhere. Decorative: the
   screens announce their own loading in words through `QueryState`, and a bar that also
   spoke would say it a second time on every refetch. This one answers the same question
   at a glance, in the one place that is on screen on every route. */
const GlobalActivityBar = () => {
  const fetching = useIsFetching();

  if (fetching === 0) {
    return null;
  }

  return (
    <span
      aria-hidden="true"
      className="absolute inset-x-0 bottom-0 h-0.5 bg-cv-accent motion-safe:animate-pulse lg:fixed lg:inset-x-0 lg:top-0 lg:bottom-auto lg:z-(--cv-z-toast)"
    />
  );
};

const SIDEBAR_ID = "app-sidebar";

/* The one control that exists only where there is a sidebar. Its name says what a press
   will do; `aria-expanded` says what the sidebar is now. */
const SidebarToggle = ({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) => {
  const label = collapsed ? "הרחבת סרגל הניווט" : "כיווץ סרגל הניווט";
  const Icon = collapsed ? PanelRightOpen : PanelRightClose;
  /* Wrapped in a tooltip in both states, not only on the rail: the button is icon-only
     either way, and a tree that changed shape on each press would remount it and drop
     the focus of the reader who just pressed it. The wrapper, not the button, carries
     the breakpoint: the button's own `inline-flex` and a `hidden` beside it would be
     settled by stylesheet order. */
  return (
    <span className="hidden lg:inline-flex">
      <Tooltip label={label} placement="rail">
        <button
          aria-controls={SIDEBAR_ID}
          aria-expanded={!collapsed}
          aria-label={label}
          className={buttonClasses("ghost", "shrink-0", "icon")}
          onClick={onToggle}
          type="button"
        >
          <Icon aria-hidden="true" className="size-icon-md" />
        </button>
      </Tooltip>
    </span>
  );
};

/* `collapsed` is only ever true at the large breakpoint (see `useSidebarCollapse`), so the
   rail classes below never reach the narrow masthead. Where a rail class replaces an
   expanded `lg:` one it replaces it outright, rather than being added beside it: two
   utilities for the same property at the same breakpoint resolve by stylesheet order,
   not by the order they are written in. */
export const AppHeader = ({ collapsed, onToggleCollapsed }: { collapsed: boolean; onToggleCollapsed: () => void }) => {
  return (
    <header
      className="sticky top-0 z-(--cv-z-navigation) border-b border-cv-hairline bg-cv-canvas/90 backdrop-blur-xl lg:col-start-1 lg:row-start-1 lg:h-screen lg:border-b-0 lg:border-e lg:bg-cv-canvas lg:backdrop-blur-none"
      id={SIDEBAR_ID}
    >
      {/* The rail drops `page-gutter`: that class is unlayered CSS, so its 2rem inline
          padding outranks any padding utility and would leave a 4.5rem column 0.5rem of
          room. It drops `flex-wrap` too - a wrapping column sizes its line to the widest
          control and pins that line to the inline-start edge instead of centring it. */}
      <div className={cx("lg:flex lg:h-full lg:flex-col lg:py-5", collapsed ? "w-full px-3" : "page-gutter lg:px-4")}>
        <div
          className={cx(
            "page-frame flex min-h-16 items-center justify-between gap-x-2 gap-y-2 py-2 sm:gap-x-4 lg:mx-0 lg:min-h-0 lg:w-full lg:flex-1 lg:flex-col lg:justify-start lg:gap-6 lg:py-0",
            collapsed ? "lg:items-center" : "flex-wrap lg:items-stretch",
          )}
        >
          <div
            className={cx(
              "flex min-w-0 items-center gap-3 sm:gap-6 lg:flex-col lg:gap-6",
              collapsed ? "lg:items-center" : "lg:items-stretch",
            )}
          >
            {/* `contents` below the large breakpoint, so the masthead lays the wordmark out
                exactly as before; on the sidebar it is the row the toggle shares. The
                rail drops the wordmark - it cannot fit, and the board it links to is the
                first navigation item anyway. */}
            <div
              className={cx(
                "contents lg:flex lg:items-center lg:gap-2",
                collapsed ? "lg:justify-center" : "lg:justify-between",
              )}
            >
              {!collapsed && (
                <Link className="group shrink-0 rounded-control" to={boardPath()}>
                  <span className="block text-heading-sm font-extrabold tracking-tight text-cv-text">קורות חיים</span>
                  <span className="block h-0.5 w-8 bg-cv-accent transition-all duration-200 group-hover:w-full" />
                </Link>
              )}
              <SidebarToggle collapsed={collapsed} onToggle={onToggleCollapsed} />
            </div>

            <div className="hidden h-5 w-px bg-cv-hairline sm:block lg:hidden" />
            <AppNavigation collapsed={collapsed} />
          </div>

          {/* In the sidebar this wraps into exactly two rows: the palette takes the
              column's full width - it is the one control here with a label to read - and
              the new-job command shares the row below it with the theme toggle. Left to
              free wrapping at a 15rem measure each control claimed a row of its own, and
              the toggle, the only one narrower than the column, sat alone against the
              opening edge reading as a stray control rather than as part of the group.
              On the rail every control is an icon, so they stack in one column. */}
          <div
            className={cx(
              "flex items-center gap-2 sm:gap-3 lg:mt-auto lg:gap-2",
              collapsed ? "lg:flex-col" : "lg:flex-wrap",
            )}
          >
            <GlobalSearch className={collapsed ? undefined : "lg:w-full"} compact={collapsed} showTrigger />

            {collapsed ? (
              <Tooltip label="משרה חדשה" placement="rail">
                <Link
                  aria-label="קליטת משרה חדשה"
                  className={buttonClasses("primary", undefined, "icon")}
                  to={routePaths.newApplication}
                >
                  <Plus aria-hidden="true" className="size-icon-md" />
                </Link>
              </Tooltip>
            ) : (
              <Link
                aria-label="קליטת משרה חדשה"
                className={buttonClasses("primary", "whitespace-nowrap lg:flex-1 lg:px-3", "default")}
                to={routePaths.newApplication}
              >
                <Plus aria-hidden="true" className="size-icon-md" />
                <span className="hidden sm:inline">משרה חדשה</span>
              </Link>
            )}

            <ThemeToggle tooltipPlacement={collapsed ? "rail" : "shell"} />
          </div>
        </div>
      </div>

      <GlobalActivityBar />
    </header>
  );
};
