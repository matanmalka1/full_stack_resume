import { type ReactNode, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { type ClassValue, cx } from "./cx";

/* Native title= gives a tooltip, but only after a long, browser-controlled delay and with
   no visual control (A.2 tone). Icon-only controls need the label to appear fast and
   consistently styled, so this wraps the trigger with a bubble of its own - no new
   dependency, shown on hover and on keyboard focus so it also serves keyboard users.

   The bubble is a manual popover, so it renders in the browser's top layer: a card with
   overflow-hidden, a sticky header or an open modal dialog cannot clip or cover it. Being
   out of the flow, it is placed in viewport coordinates from the trigger's box, turned to
   the other side when its own side has no room, and kept inside the viewport. */
interface TooltipProps {
  /* Which edge of the trigger the bubble lines up with on the inline axis. The default is
     the trigger's closing edge, so the bubble opens back across the page; either way it is
     kept inside the viewport. */
  align?: "center" | "end";
  children: ReactNode;
  className?: ClassValue;
  label: string;
  /* Which side of the trigger the bubble prefers; it flips when that side has no room. */
  placement?: "top" | "bottom";
  /* A label longer than a control's name - a list of reasons, a full date - wraps at a
     reading measure instead of running off as one line. */
  wrap?: boolean;
}

const GAP = 8;
const EDGE = 8;
const SHOW_DELAY_MS = 300;

const canPopover = () => typeof HTMLElement !== "undefined" && "showPopover" in HTMLElement.prototype;

const place = (
  trigger: HTMLElement,
  bubble: HTMLElement,
  align: TooltipProps["align"],
  placement: TooltipProps["placement"],
) => {
  const anchor = trigger.getBoundingClientRect();
  const { height, width } = bubble.getBoundingClientRect();
  const viewportWidth = document.documentElement.clientWidth;
  const viewportHeight = document.documentElement.clientHeight;

  const roomAbove = anchor.top - GAP - EDGE >= height;
  const roomBelow = anchor.bottom + GAP + height + EDGE <= viewportHeight;
  const above = placement === "top" ? roomAbove || !roomBelow : !roomBelow && roomAbove;
  const top = above ? anchor.top - GAP - height : anchor.bottom + GAP;

  const rtl = getComputedStyle(trigger).direction === "rtl";
  const left =
    align === "center" ? anchor.left + anchor.width / 2 - width / 2 : rtl ? anchor.left : anchor.right - width;

  bubble.style.top = `${Math.round(top)}px`;
  bubble.style.left = `${Math.round(Math.min(Math.max(left, EDGE), viewportWidth - EDGE - width))}px`;
};

export const Tooltip = ({
  align = "end",
  children,
  className,
  label,
  placement = "top",
  wrap = false,
}: TooltipProps) => {
  const triggerRef = useRef<HTMLSpanElement>(null);
  const bubbleRef = useRef<HTMLSpanElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const [open, setOpen] = useState(false);

  const show = useCallback(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setOpen(true), SHOW_DELAY_MS);
  }, []);
  const hide = useCallback(() => {
    window.clearTimeout(timer.current);
    setOpen(false);
  }, []);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  useLayoutEffect(() => {
    const bubble = bubbleRef.current;
    const trigger = triggerRef.current;
    if (!open || bubble === null || trigger === null || !canPopover()) {
      return;
    }
    bubble.showPopover();
    const update = () => place(trigger, bubble, align, placement);
    update();
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && hide();
    // The bubble is fixed to the viewport; anything that moves the trigger closes it.
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", update);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("scroll", hide, true);
      window.removeEventListener("resize", update);
      window.removeEventListener("keydown", onKey);
      if (bubble.matches(":popover-open")) {
        bubble.hidePopover();
      }
    };
  }, [align, hide, open, placement]);

  return (
    <span
      className={cx("relative inline-flex", className)}
      onBlur={hide}
      onFocus={(event) => {
        // A click focuses the button too; only keyboard focus should raise the bubble.
        if (event.target.matches(":focus-visible")) {
          show();
        }
      }}
      onPointerDown={hide}
      onPointerEnter={(event) => event.pointerType !== "touch" && show()}
      onPointerLeave={hide}
      ref={triggerRef}
    >
      {children}
      <span
        className={cx(
          "pointer-events-none fixed inset-auto m-0 rounded-control border-0 bg-cv-text px-2 py-1 text-support font-medium text-cv-on-accent opacity-100 shadow-floating transition-opacity duration-150 starting:opacity-0",
          wrap ? "w-max max-w-72 whitespace-normal" : "whitespace-nowrap",
        )}
        popover="manual"
        ref={bubbleRef}
        role="tooltip"
      >
        {label}
      </span>
    </span>
  );
};
