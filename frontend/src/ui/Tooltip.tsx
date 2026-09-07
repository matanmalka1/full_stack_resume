import type { ReactNode } from "react";

import { type ClassValue, cx } from "./cx";

/* Native title= gives a tooltip, but only after a long, browser-controlled delay and with
   no visual control (A.2 tone). Icon-only controls need the label to appear fast and
   consistently styled, so this wraps the trigger with a CSS-only bubble instead - no new
   dependency, shown/hidden by :hover and :focus-visible so it also serves keyboard users. */
interface TooltipProps {
  children: ReactNode;
  className?: ClassValue;
  label: string;
  placement?: "top" | "bottom";
}

const placementClasses = {
  bottom: "top-full mt-2",
  top: "bottom-full mb-2",
} as const;

export const Tooltip = ({ children, className, label, placement = "top" }: TooltipProps) => (
  <span className={cx("group/tooltip relative inline-flex", className)}>
    {children}
    <span
      className={cx(
        "pointer-events-none absolute start-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded-control bg-cv-text px-2 py-1 text-support font-medium text-cv-on-accent opacity-0 shadow-floating transition-opacity delay-0 duration-150 group-hover/tooltip:delay-300 group-hover/tooltip:opacity-100 group-focus-within/tooltip:delay-300 group-focus-within/tooltip:opacity-100 rtl:translate-x-1/2",
        placementClasses[placement],
      )}
      role="tooltip"
    >
      {label}
    </span>
  </span>
);
