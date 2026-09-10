import type { ReactNode } from "react";

import { type ClassValue, cx } from "./cx";

/* Native title= gives a tooltip, but only after a long, browser-controlled delay and with
   no visual control (A.2 tone). Icon-only controls need the label to appear fast and
   consistently styled, so this wraps the trigger with a CSS-only bubble instead - no new
   dependency, shown/hidden by :hover and :focus-visible so it also serves keyboard users. */
interface TooltipProps {
  /* Which edge of the trigger the bubble hangs from on the inline axis.

     The default is the trigger's closing edge, so the bubble opens back across the page.
     A tooltip is always wider than the icon button it names, and the controls that need
     one are the icon-only ones - which is to say the ones at an edge: the masthead's
     theme toggle, a table row's overflow menu. Centred on those, half the bubble hung
     off the viewport and gave the whole document a horizontal scrollbar while remaining
     invisible at rest. "center" stays available for a trigger with room on both sides. */
  align?: "center" | "end";
  children: ReactNode;
  className?: ClassValue;
  label: string;
  /* Which side of the trigger the bubble hangs on. "shell" is the shell's own case: the
     masthead's controls sit at the top of a narrow page and at the foot of the sidebar on
     a wide one, so the bubble has to hang down in the first and up in the second, or it
     leaves the viewport at whichever end it is pinned to. */
  placement?: "top" | "bottom" | "shell";
}

const alignClasses = {
  center: "start-1/2 -translate-x-1/2 rtl:translate-x-1/2",
  end: "end-0",
} as const;

const placementClasses = {
  bottom: "top-full mt-2",
  shell: "top-full mt-2 lg:top-auto lg:bottom-full lg:mt-0 lg:mb-2",
  top: "bottom-full mb-2",
} as const;

export const Tooltip = ({ align = "end", children, className, label, placement = "top" }: TooltipProps) => (
  <span className={cx("group/tooltip relative inline-flex", className)}>
    {children}
    <span
      className={cx(
        "pointer-events-none absolute z-(--cv-z-content-raised) whitespace-nowrap rounded-control bg-cv-text px-2 py-1 text-support font-medium text-cv-on-accent opacity-0 shadow-floating transition-opacity delay-0 duration-150 group-hover/tooltip:delay-300 group-hover/tooltip:opacity-100 group-focus-within/tooltip:delay-300 group-focus-within/tooltip:opacity-100",
        alignClasses[align],
        placementClasses[placement],
      )}
      role="tooltip"
    >
      {label}
    </span>
  </span>
);
