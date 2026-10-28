import { useIsFetching } from "@tanstack/react-query";
import { FileText, PanelRightClose, PanelRightOpen, Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { buttonClasses } from "@/ui/Button";
import { cx } from "@/ui/cx";
import { Tooltip } from "@/ui/Tooltip";
import { SignOutButton } from "@/features/auth";
import { GlobalSearch } from "../search/GlobalSearch";
import { boardPath } from "@/navigation/boardReturn";
import { routePaths } from "@/navigation/routePaths";
import { AppNavigation } from "./AppNavigation";

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
   not by the order they are written in.

   `hiddenOnPhone` drops the whole header - masthead and bottom navigation, which lives
   inside it - below the large breakpoint, for a screen that brings its own. */
export const AppHeader = ({
  collapsed,
  hiddenOnPhone = false,
  onToggleCollapsed,
}: {
  collapsed: boolean;
  hiddenOnPhone?: boolean;
  onToggleCollapsed: () => void;
}) => {
  return (
    <header
      className={cx(
        "sticky top-0 z-(--cv-z-navigation) bg-cv-canvas lg:col-start-1 lg:row-start-1 lg:h-screen lg:border-e lg:border-cv-hairline lg:bg-cv-surface",
        hiddenOnPhone && "max-lg:hidden",
      )}
      id={SIDEBAR_ID}
    >
      {/* The sidebar does not use `page-gutter`: that class is unlayered CSS, so its 2rem
          inline padding outranks any padding utility and would leave the column's controls
          a third narrower than it. The masthead keeps the gutter's own steps below the
          large breakpoint through plain utilities instead. The rail drops `flex-wrap` too -
          a wrapping column sizes its line to the widest control and pins that line to the
          inline-start edge instead of centring it. */}
      <div className={cx("w-full lg:flex lg:h-full lg:flex-col lg:py-5", collapsed ? "px-3" : "px-4 sm:px-6 lg:px-4")}>
        <div
          className={cx(
            "page-frame flex min-h-16 items-center justify-between gap-x-2 gap-y-2 py-2 sm:gap-x-4 lg:mx-0 lg:min-h-0 lg:w-full lg:flex-1 lg:flex-col lg:justify-start lg:gap-4 lg:py-0",
            collapsed ? "lg:items-center" : "flex-wrap lg:items-stretch",
          )}
        >
          {/* The sidebar reads top to bottom as the design draws it: the wordmark, the
              new-job command, the quick switcher, the destinations, and sign-out at the
              foot. The two groups below keep the masthead's own order on a phone - the
              wordmark at one end, the switcher at the other - and become `contents` on the
              sidebar, so each control is one of its items and `order` places it. */}
          <div className="flex min-w-0 items-center gap-3 sm:gap-6 lg:contents">
            {/* The rail drops the wordmark - it cannot fit, and the board it links to is the
                first navigation item anyway. */}
            <div
              className={cx(
                "contents lg:order-1 lg:flex lg:items-center lg:gap-2",
                collapsed ? "lg:justify-center" : "lg:justify-between",
              )}
            >
              {!collapsed && (
                <Link className="flex min-w-0 shrink-0 items-center gap-2.5 rounded-control" to={boardPath()}>
                  <span
                    aria-hidden="true"
                    className="flex size-9 shrink-0 items-center justify-center rounded-control bg-cv-accent text-cv-on-accent"
                  >
                    <FileText className="size-icon-md" />
                  </span>
                  <span className="truncate text-heading-sm font-extrabold tracking-tight text-cv-text">
                    קורות חיים
                  </span>
                </Link>
              )}
              <SidebarToggle collapsed={collapsed} onToggle={onToggleCollapsed} />
            </div>

            <div className="contents lg:order-4 lg:block">
              <AppNavigation collapsed={collapsed} />
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3 lg:contents">
            {/* On a narrow screen the masthead keeps the wordmark and the quick switcher,
                there an icon - its label and shortcut hint fold away below `md`. Sign-out
                moves to Settings and the new-job command to the board's floating button. */}
            <GlobalSearch
              className={collapsed ? undefined : "max-lg:size-11 max-lg:justify-center max-lg:px-0 lg:w-full"}
              compact={collapsed}
              showTrigger
              triggerWrapperClassName={cx("flex lg:order-3", collapsed ? "lg:justify-center" : "lg:w-full")}
            />
            <span className={cx("hidden lg:order-5 lg:mt-auto lg:flex", collapsed ? "lg:justify-center" : "lg:w-full")}>
              <SignOutButton compact={collapsed} />
            </span>

            {collapsed ? (
              <span className="hidden lg:order-2 lg:flex lg:justify-center">
                <Tooltip label="משרה חדשה" placement="rail">
                  <Link
                    aria-label="קליטת משרה חדשה"
                    className={buttonClasses("primary", undefined, "icon")}
                    to={routePaths.newApplication}
                  >
                    <Plus aria-hidden="true" className="size-icon-md" />
                  </Link>
                </Tooltip>
              </span>
            ) : (
              /* The wrapper carries the breakpoint, for the reason `SidebarToggle` gives. */
              <span className="hidden lg:order-2 lg:flex">
                <Link
                  aria-label="קליטת משרה חדשה"
                  className={buttonClasses("primary", "min-h-11 flex-1 whitespace-nowrap lg:px-3", "default")}
                  to={routePaths.newApplication}
                >
                  <Plus aria-hidden="true" className="size-icon-md" />
                  <span>משרה חדשה</span>
                </Link>
              </span>
            )}
          </div>
        </div>
      </div>

      <GlobalActivityBar />
    </header>
  );
};
