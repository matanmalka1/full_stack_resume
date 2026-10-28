import { useSyncExternalStore } from "react";

/* Below the large breakpoint - the same line Tailwind's `max-lg:` draws.

   Most of a phone's layout is CSS on the same tree. The run's report is the exception:
   on a phone a failure is a page of its own, worded differently from the wide report, and
   drawing both trees and hiding one would put every sentence in the document twice. This
   chooses one tree instead. Where `matchMedia` is missing (jsdom) the answer is the wide
   layout, which is what the component tests describe. */
const QUERY = "not all and (min-width: 64rem)";

const subscribe = (onChange: () => void): (() => void) => {
  if (typeof window.matchMedia !== "function") return () => undefined;
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
};

const snapshot = (): boolean => typeof window.matchMedia === "function" && window.matchMedia(QUERY).matches;

export const useIsPhone = (): boolean => useSyncExternalStore(subscribe, snapshot, () => false);
