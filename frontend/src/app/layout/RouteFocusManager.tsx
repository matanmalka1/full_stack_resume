import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

/* A.2: focus moves to the page heading after a route change - and only after one.

   The screen the application opened on is not a navigation: nobody was moved there, so
   focusing its heading only drew a focus ring over the first paint of every visit. The
   entry path is remembered until the first real navigation, which is also what keeps the
   skip from surviving into a later return to that same path. */
export const RouteFocusManager = () => {
  const { pathname } = useLocation();
  const entryPathname = useRef<string | null>(pathname);

  useEffect(() => {
    if (entryPathname.current === pathname) {
      return;
    }

    entryPathname.current = null;

    const frameId = window.requestAnimationFrame(() => {
      document.querySelector<HTMLElement>("[data-route-heading]")?.focus();
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [pathname]);

  return null;
};
