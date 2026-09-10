import { useEffect, useRef } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

export const RouteFocusManager = () => {
  const { pathname } = useLocation();
  const navigationType = useNavigationType();
  const entryPathname = useRef<string | null>(pathname);

  useEffect(() => {
    if (entryPathname.current === pathname) {
      return;
    }

    /* A POP (back/forward) restores a page the reader already scrolled and focused -
       resetting either here would throw away what the browser's own history just gave
       back. */
    if (navigationType === "POP") {
      entryPathname.current = pathname;
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
