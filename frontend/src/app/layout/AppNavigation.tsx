import { BookOpen, LayoutDashboard, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";

import { cx } from "@/ui/cx";
import { boardPath } from "../boardReturn";
import { routePaths } from "../routePaths";

/* The application's main areas, and all of them. Everything else is one Application's
   own screen, reached from the board rather than from the shell, so listing it here
   would offer a destination that means nothing until a record is chosen.

   Two entries need no configuration system; the list is here so the header renders one
   markup rather than two near-copies. It is built per render rather than at module scope
   because the board entry carries the filtering the reader left the board under, which is
   not knowable when this module loads. `NavLink` decides `isActive` from the path alone,
   so the query changes nothing about the active state it draws - and each entry keeps a
   `key` of its own so a changing query does not remount the link. */
const areas = () => [
  { icon: LayoutDashboard, key: routePaths.home, label: "לוח המועמדויות", to: boardPath() },
  { icon: BookOpen, key: routePaths.facts, label: "מאגר העובדות", to: routePaths.facts },
  { icon: Settings, key: routePaths.settings, label: "הגדרות", to: routePaths.settings },
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
    {areas().map(({ icon: Icon, key, label, to }) => (
      <NavLink aria-label={label} className={({ isActive }) => linkClasses(isActive)} end key={key} to={to}>
        <Icon aria-hidden="true" className="size-4 shrink-0" />
        <span className="hidden sm:inline">{label}</span>
      </NavLink>
    ))}
  </nav>
);
