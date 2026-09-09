import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

export const RouteFocusManager = () => {
  const { pathname } = useLocation();
  const entryPathname = useRef<string | null>(pathname);

  useEffect(() => {
    if (entryPathname.current === pathname) {
      return;
    }

    entryPathname.current = null;

    const frameId = window.requestAnimationFrame(() => {
      window.scrollTo({ left: 0, top: 0 });
      document.querySelector<HTMLElement>("[data-route-heading]")?.focus({ preventScroll: true });
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [pathname]);

  return null;
};
