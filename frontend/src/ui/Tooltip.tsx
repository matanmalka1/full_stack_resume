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
}

export const Tooltip = ({ children, className, label }: TooltipProps) => (
  <span className={cx("group relative inline-flex", className)}>
    {children}
    <span
      className="pointer-events-none absolute bottom-full start-1/2 z-10 mb-2 -translate-x-1/2 rtl:translate-x-1/2 whitespace-nowrap rounded-control bg-cv-text px-2 py-1 text-support font-medium text-cv-on-accent opacity-0 shadow-floating transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
      role="tooltip"
    >
      {label}
    </span>
  </span>
);
