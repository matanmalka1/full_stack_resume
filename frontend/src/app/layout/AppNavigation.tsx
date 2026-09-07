import { LayoutDashboard, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";

import { cx } from "@/ui/cx";
import { routePaths } from "../routePaths";

/* The application's main areas, and all of them. Everything else is one Application's
   own screen, reached from the board rather than from the shell, so listing it here
   would offer a destination that means nothing until a record is chosen.

   Two entries need no configuration system; the array is here so the header renders one
   markup rather than two near-copies. */
const areas = [
  { icon: LayoutDashboard, label: "לוח המועמדויות", to: routePaths.home },
  { icon: Settings, label: "הגדרות", to: routePaths.settings },
];

const linkClasses = (isActive: boolean): string =>
  cx(
    "inline-flex items-center gap-2 rounded-control px-2.5 py-1.5 text-support font-semibold transition-colors sm:px-3",
    isActive ? "bg-cv-accent-soft text-cv-accent" : "text-cv-text-muted hover:bg-cv-surface-muted hover:text-cv-text",
  );

/* Active state comes from the router - `NavLink` also sets `aria-current="page"` - so
   nothing here mirrors the location in state of its own.
   
   Each link carries its label as `aria-label` too, because the visible one is hidden on a
   narrow screen and a link whose only name is display:none text has no name at all. */
export const AppNavigation = () => (
  <nav aria-label="ניווט ראשי" className="flex items-center gap-1">
    {areas.map(({ icon: Icon, label, to }) => (
      <NavLink aria-label={label} className={({ isActive }) => linkClasses(isActive)} end key={to} to={to}>
        <Icon aria-hidden="true" className="size-4 shrink-0" />
        <span className="hidden sm:inline">{label}</span>
      </NavLink>
    ))}
  </nav>
);
