import { BookOpen, LayoutDashboard, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";

import { cx } from "@/ui/cx";
import { Tooltip } from "@/ui/Tooltip";
import { boardPath } from "../boardReturn";
import { routePaths } from "../routePaths";

const areas = () => [
  { icon: LayoutDashboard, key: routePaths.home, label: "לוח המועמדויות", to: boardPath() },
  { icon: BookOpen, key: routePaths.facts, label: "מאגר העובדות", to: routePaths.facts },
  { icon: Settings, key: routePaths.settings, label: "הגדרות", to: routePaths.settings },
];

const linkClasses = (isActive: boolean, collapsed: boolean): string =>
  cx(
    "inline-flex items-center gap-2 border-s-2 text-support transition-colors",
    collapsed ? "size-11 justify-center" : "min-h-11 px-2 sm:px-3 lg:min-h-0 lg:py-2",
    isActive
      ? "border-s-cv-nav-active-indicator bg-cv-nav-active-bg font-bold text-cv-text"
      : "border-s-transparent font-medium text-cv-text-muted hover:bg-cv-surface-muted hover:text-cv-text",
  );

/* Active state comes from the router - `NavLink` also sets `aria-current="page"` - so
   nothing here mirrors the location in state of its own.
   
   Each link carries its label as `aria-label` too, because the visible one is hidden on a
   narrow screen and on the collapsed rail, and a link whose only name is display:none
   text has no name at all. On the rail - which only exists at the large breakpoint - the
   icon stands in for the label and a tooltip gives the label back on hover and focus. */
export const AppNavigation = ({ collapsed = false }: { collapsed?: boolean }) => (
  <nav
    aria-label="ניווט ראשי"
    className={cx("flex items-center gap-0.5 sm:gap-1 lg:flex-col", collapsed ? "lg:items-center" : "lg:items-stretch")}
  >
    {areas().map(({ icon: Icon, key, label, to }) => {
      const link = (
        <NavLink
          aria-label={label}
          className={({ isActive }) => linkClasses(isActive, collapsed)}
          end
          key={key}
          to={to}
        >
          <Icon aria-hidden="true" className={cx("size-icon-md shrink-0", !collapsed && "sm:hidden")} />
          {!collapsed && <span className="hidden sm:inline">{label}</span>}
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
