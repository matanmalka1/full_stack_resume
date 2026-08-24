import { useEffect } from "react";
import { useLocation } from "react-router-dom";

export const RouteFocusManager = () => {
  const { pathname } = useLocation();

  useEffect(() => {
    const frameId = window.requestAnimationFrame(() => {
      document.querySelector<HTMLElement>("[data-route-heading]")?.focus();
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [pathname]);

  return null;
};
