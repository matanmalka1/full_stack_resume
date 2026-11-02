import { useSyncExternalStore } from "react";

/* Below the large breakpoint - the same line Tailwind's `max-lg:` draws.

   Most of a phone's layout is CSS on one tree. This is for the exception: a command the
   design places in a different part of the page at each width - the draft's approval, in
   the heading on a wide screen and in the bar pinned to a phone's bottom edge. Drawing it
   in both places and hiding one would put the same command in the document twice. Where
   `matchMedia` is missing (jsdom) the answer is the wide layout, which is what the
   component tests describe.

   The operations feature keeps its own copy (`features/operations/hooks/useIsPhone`);
   the two should become this one. */
const QUERY = "not all and (min-width: 64rem)";

const subscribe = (onChange: () => void): (() => void) => {
  if (typeof window.matchMedia !== "function") return () => undefined;
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
};

const snapshot = (): boolean => typeof window.matchMedia === "function" && window.matchMedia(QUERY).matches;

export const useIsPhone = (): boolean => useSyncExternalStore(subscribe, snapshot, () => false);
