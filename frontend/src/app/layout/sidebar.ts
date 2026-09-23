import { useCallback, useState, useSyncExternalStore } from "react";

/* Whether the desktop sidebar is folded down to its icon rail.

   The preference is the reader's own and belongs to this browser, so it is kept in local
   storage rather than in Settings: it is a layout convenience, not a value the engine or
   any other device needs. Storage may be blocked; the sidebar then simply opens expanded
   and a toggle still works for the rest of the visit.

   It applies only where there is a sidebar. Below the large breakpoint the shell is a
   horizontal masthead, and a preference saved on a wide window must not reach it - so
   the answer is "collapsed" only when the preference is set AND the viewport is wide. */
const SIDEBAR_COLLAPSED_KEY = "cv-sidebar-collapsed";

/* Tailwind's `lg` breakpoint, which is where AppLayout switches to the sidebar grid. */
const WIDE_QUERY = "(min-width: 64rem)";

const readCollapsed = (): boolean => {
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
  } catch {
    return false;
  }
};

const storeCollapsed = (collapsed: boolean) => {
  try {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(collapsed));
  } catch {
    /* Optional; the choice then lasts for this visit only. */
  }
};

const subscribeWide = (onChange: () => void) => {
  if (typeof window.matchMedia !== "function") return () => undefined;
  const query = window.matchMedia(WIDE_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
};

const isWide = () => typeof window.matchMedia === "function" && window.matchMedia(WIDE_QUERY).matches;

export const useSidebarCollapse = () => {
  const wide = useSyncExternalStore(subscribeWide, isWide, () => false);
  const [preference, setPreference] = useState(readCollapsed);

  const toggle = useCallback(() => {
    const next = !preference;
    setPreference(next);
    storeCollapsed(next);
  }, [preference]);

  return { collapsed: wide && preference, toggle };
};
