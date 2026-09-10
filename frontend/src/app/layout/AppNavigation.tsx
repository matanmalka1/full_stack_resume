import { BookOpen, LayoutDashboard, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";

import { cx } from "@/ui/cx";
import { boardPath } from "../boardReturn";
import { routePaths } from "../routePaths";

const areas = () => [
  { icon: LayoutDashboard, key: routePaths.home, label: "לוח המועמדויות", to: boardPath() },
  { icon: BookOpen, key: routePaths.facts, label: "מאגר העובדות", to: routePaths.facts },
  { icon: Settings, key: routePaths.settings, label: "הגדרות", to: routePaths.settings },
];

const linkClasses = (isActive: boolean): string =>
  cx(
    "inline-flex items-center gap-2 border-s-2 px-2.5 py-2 text-support transition-colors sm:px-3",
    isActive
      ? "border-s-cv-nav-active-indicator bg-cv-nav-active-bg font-bold text-cv-text"
      : "border-s-transparent font-medium text-cv-text-muted hover:bg-cv-surface-muted hover:text-cv-text",
  );

/* Active state comes from the router - `NavLink` also sets `aria-current="page"` - so
   nothing here mirrors the location in state of its own.
   
   Each link carries its label as `aria-label` too, because the visible one is hidden on a
   narrow screen and a link whose only name is display:none text has no name at all. */
export const AppNavigation = () => (
  <nav aria-label="ניווט ראשי" className="flex items-center gap-1 lg:flex-col lg:items-stretch">
    {areas().map(({ icon: Icon, key, label, to }) => (
      <NavLink aria-label={label} className={({ isActive }) => linkClasses(isActive)} end key={key} to={to}>
        <Icon aria-hidden="true" className="size-icon-md shrink-0 sm:hidden" />
        <span className="hidden sm:inline">{label}</span>
      </NavLink>
    ))}
  </nav>
);
