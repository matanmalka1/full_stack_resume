import { BookOpen, LayoutDashboard, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";

import { cx } from "@/ui/cx";
import { Tooltip } from "@/ui/Tooltip";
import { boardPath } from "@/navigation/boardReturn";
import { routePaths } from "@/navigation/routePaths";

const areas = () => [
  { icon: LayoutDashboard, key: routePaths.home, label: "לוח המועמדויות", short: "לוח", to: boardPath() },
  { icon: BookOpen, key: routePaths.facts, label: "מאגר העובדות", short: "עובדות", to: routePaths.facts },
  { icon: Settings, key: routePaths.settings, label: "הגדרות", short: "הגדרות", to: routePaths.settings },
];

/* Below the large breakpoint each link is one cell of the bottom bar: the icon over a
   short label, sharing the bar's width equally. From the breakpoint it is a row of the
   sidebar - its icon, then its label - with the indicator on its inline-start edge. */
const linkClasses = (isActive: boolean, collapsed: boolean): string =>
  cx(
    "inline-flex items-center rounded-control transition-colors",
    "min-w-0 flex-1 flex-col justify-center gap-0.5 text-caption lg:flex-none lg:flex-row lg:border-s-2 lg:text-support",
    collapsed ? "lg:size-11 lg:justify-center" : "lg:min-h-10 lg:justify-start lg:gap-2.5 lg:px-3",
    isActive
      ? "font-bold text-cv-text lg:border-cv-nav-active-indicator lg:bg-cv-nav-active-bg"
      : "font-medium text-cv-text-muted hover:text-cv-text lg:border-transparent lg:hover:bg-cv-surface-muted",
  );

/* Below the large breakpoint the navigation is a bar pinned to the bottom of the viewport,
   where a thumb reaches it and every destination keeps a visible label; the masthead
   above keeps only the wordmark and the new-job command. Its height is the shell's
   `--cv-bottom-nav-height`, which every other bottom-pinned surface stands on. At the
   large breakpoint the same element becomes the sidebar's list.

   Active state comes from the router - `NavLink` also sets `aria-current="page"` - so
   nothing here mirrors the location in state of its own.

   Each link carries its full label as `aria-label`, because the bottom bar shows a short
   one and the collapsed rail shows none. On the rail - which only exists at the large
   breakpoint - the icon stands in for the label and a tooltip gives it back on hover and
   focus. */
export const AppNavigation = ({ collapsed = false }: { collapsed?: boolean }) => (
  <nav
    aria-label="ניווט ראשי"
    className={cx(
      "fixed inset-x-0 bottom-0 z-(--cv-z-navigation) flex h-(--cv-bottom-nav-height) items-stretch gap-1 border-t border-cv-hairline bg-cv-canvas px-2 pt-1 pb-[calc(env(safe-area-inset-bottom,0px)+0.25rem)]",
      "lg:static lg:h-auto lg:flex-col lg:gap-1 lg:border-t-0 lg:bg-transparent lg:p-0",
      collapsed ? "lg:items-center" : "lg:items-stretch",
    )}
  >
    {areas().map(({ icon: Icon, key, label, short, to }) => {
      const link = (
        <NavLink
          aria-label={label}
          className={({ isActive }) => linkClasses(isActive, collapsed)}
          end
          key={key}
          to={to}
        >
          {({ isActive }) => (
            <>
              <span
                className={cx(
                  "inline-flex h-7 w-12 items-center justify-center rounded-pill transition-colors lg:h-auto lg:w-auto",
                  isActive && "bg-cv-nav-active-bg lg:bg-transparent",
                )}
              >
                <Icon aria-hidden="true" className="size-icon-md shrink-0" />
              </span>
              {collapsed ? null : (
                <>
                  <span className="max-w-full truncate lg:hidden">{short}</span>
                  <span className="hidden lg:inline">{label}</span>
                </>
              )}
            </>
          )}
        </NavLink>
      );
      return collapsed ? (
        <Tooltip key={key} label={label} placement="rail">
          {link}
        </Tooltip>
      ) : (
        link
      );
    })}
  </nav>
);
