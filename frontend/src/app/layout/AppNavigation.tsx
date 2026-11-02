import { BookOpen, LayoutDashboard, Settings } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { cx } from "@/ui/cx";
import { boardPath } from "@/navigation/boardReturn";
import { routePaths } from "@/navigation/routePaths";

/* `within` names the addresses that sit under an area without being its own page: an
   Application and its steps are reached from the board, so the board stays marked
   there. */
const areas = () => [
  {
    icon: LayoutDashboard,
    key: routePaths.home,
    label: "לוח המועמדויות",
    short: "לוח",
    to: boardPath(),
    within: (pathname: string) => pathname.startsWith("/applications/"),
  },
  { icon: BookOpen, key: routePaths.facts, label: "מאגר העובדות", short: "עובדות", to: routePaths.facts, within: null },
  { icon: Settings, key: routePaths.settings, label: "הגדרות", short: "הגדרות", to: routePaths.settings, within: null },
];

/* Below the large breakpoint each link is one cell of the tab bar: the icon in a pill
   over a short label, sharing the bar's width equally. From the breakpoint it is a row of
   the sidebar, icon then label, with the indicator on its inline-start edge. */
const linkClasses = (isActive: boolean): string =>
  cx(
    "flex min-w-0 flex-1 flex-col items-center justify-center gap-0.5 text-caption transition-colors",
    "lg:min-h-10 lg:flex-none lg:flex-row lg:justify-start lg:gap-2.5 lg:rounded-item lg:border-s-2 lg:px-3 lg:text-label",
    isActive
      ? "font-bold text-cv-text lg:border-cv-nav-active-indicator lg:bg-cv-nav-active-bg"
      : "font-medium text-cv-text-muted hover:text-cv-text lg:border-transparent lg:hover:bg-cv-surface-muted",
  );

/* Below the large breakpoint the navigation is a tab bar pinned to the bottom of the
   viewport, where a thumb reaches it and every destination keeps a visible label. Its
   height is the shell's `--cv-bottom-nav-height`, which every other bottom-pinned surface
   stands on. At the large breakpoint the same element becomes the sidebar's list.

   Active state is read from the router's location, so nothing here mirrors it in state
   of its own. On an area's own page its link is `aria-current="page"`; under the area but
   off that page it is marked as where the reader is (`aria-current="true"`). Each link carries its full label
   as `aria-label`, because the tab bar shows a short one. */
export const AppNavigation = () => {
  const { pathname } = useLocation();

  return (
    <nav
      aria-label="ניווט ראשי"
      className={cx(
        "fixed inset-x-0 bottom-0 z-(--cv-z-navigation) flex h-(--cv-bottom-nav-height) items-stretch gap-1 border-t border-cv-hairline bg-cv-surface/95 px-2 pt-2 pb-[calc(env(safe-area-inset-bottom,0px)+0.5rem)] backdrop-blur",
        "lg:static lg:h-auto lg:flex-col lg:gap-0.5 lg:border-t-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none",
      )}
    >
      {areas().map(({ icon: Icon, key, label, short, to, within }) => {
        const isPage = pathname === key;
        const isActive = isPage || (within?.(pathname) ?? false);
        return (
          <Link
            aria-current={isPage ? "page" : isActive ? "true" : undefined}
            aria-label={label}
            className={linkClasses(isActive)}
            key={key}
            to={to}
          >
            <span
              className={cx(
                "flex h-7.5 w-14 shrink-0 items-center justify-center rounded-pill transition-colors lg:size-auto",
                isActive && "bg-cv-nav-active-bg lg:bg-transparent",
              )}
            >
              <Icon aria-hidden="true" className="size-5 lg:size-4.5" />
            </span>
            <span className="max-w-full truncate lg:hidden">{short}</span>
            <span className="hidden truncate lg:inline">{label}</span>
          </Link>
        );
      })}
    </nav>
  );
};
