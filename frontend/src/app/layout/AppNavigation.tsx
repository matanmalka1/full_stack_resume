import { BookOpen, FileText, Settings } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { cx } from "@/ui/cx";
import { routePaths } from "@/navigation/routePaths";

/* `within` names the addresses that sit under an area without being its own page: an
   Application and its steps are reached from the CV library, so the library stays marked
   there. */
const areas = () => [
  {
    icon: FileText,
    key: routePaths.home(),
    label: "קורות החיים",
    short: "קו״ח",
    to: routePaths.home(),
    within: (pathname: string) => pathname.startsWith("/applications/"),
  },
  { icon: BookOpen, key: routePaths.facts, label: "מאגר העובדות", short: "עובדות", to: routePaths.facts, within: null },
  { icon: Settings, key: routePaths.settings, label: "הגדרות", short: "הגדרות", to: routePaths.settings, within: null },
];

/* Below the large breakpoint each link is one cell of the floating glass bar: the icon
   over a short label, sharing the bar's width equally, the active one in a glass capsule
   of its own (`cv-glass-pill`). From the breakpoint it is a row of the sidebar, icon then
   label, with the indicator on its inline-start edge. */
const linkClasses = (isActive: boolean): string =>
  cx(
    "flex min-w-0 flex-1 flex-col items-center justify-center gap-0.5 rounded-pill text-caption transition-[color,background-color,box-shadow,scale] duration-200",
    "active:scale-95 motion-reduce:active:scale-100",
    isActive && "cv-glass-pill",
    "lg:min-h-10 lg:flex-none lg:flex-row lg:justify-start lg:gap-2.5 lg:rounded-item lg:border-s-2 lg:px-3 lg:text-label",
    isActive
      ? "font-bold text-cv-text lg:border-cv-nav-active-indicator lg:bg-cv-nav-active-bg"
      : "font-medium text-cv-text-muted hover:text-cv-text lg:border-transparent lg:hover:bg-cv-surface-muted",
  );

/* Below the large breakpoint the navigation is a capsule of glass floating over the
   bottom of the viewport, as on the iPhone, where a thumb reaches it and every destination
   keeps a visible label (`cv-glass-bar`). The room it takes, gaps included, is the
   shell's `--cv-bottom-nav-height`, which every other bottom-pinned surface stands on. At the large breakpoint the same element becomes the sidebar's list.

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
        "cv-glass-bar fixed inset-x-4 bottom-(--cv-bottom-nav-gap) z-(--cv-z-navigation) mx-auto flex h-(--cv-bottom-nav-bar) max-w-md items-stretch gap-1 rounded-pill p-1.5",
        "lg:static lg:mx-0 lg:h-auto lg:max-w-none lg:flex-col lg:gap-0.5 lg:rounded-none lg:p-0",
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
                "flex h-6 shrink-0 items-center justify-center lg:size-auto",
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

/* The name of the area the reader is in, for the phone's top bar, which titles the screen
   the way an iPhone's navigation bar does. Undefined off every area (the not-found page). */
export const areaTitle = (pathname: string): string | undefined =>
  areas().find(({ key, within }) => pathname === key || (within?.(pathname) ?? false))?.label;
