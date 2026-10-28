import { createContext, useContext, useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { cx } from "./cx";
import { LiveRegion } from "./LiveRegion";

/* What every pinned bar in the flow calls itself when it is a wizard step's action rather
   than a form's commit. Named "מה עושים עכשיו" and not "הצעד הבא": the bar carries the
   action the current step is waiting on, not the step after it, and the board already
   spends "הצעד הבא" on a recruitment reminder that has nothing to do with the CV work. */
export const NEXT_STEP_LABEL = "מה עושים עכשיו";

interface CommitBarProps {
  /* The draft's embedded decision keeps its commit beside the form. */
  inline?: boolean;
  /* The way back to the previous step, ahead of everything else on the opening edge. A
     wizard that only goes forward is a form; what makes the spine navigable in both
     directions has to be true of the bar as well.

     Absent on a bar that commits a decision rather than closing a step, and absent on the
     first step with a record - the intake behind it created the Application, and
     re-entering it would not be going back. */
  back?: ReactNode;
  /* False drops `back` below the large breakpoint, so the command takes the bar's whole
     width there - a phone reaches the previous step through the screen's own back link,
     and a bar holding both left the command a narrow button in a corner. */
  backOnPhone?: boolean;
  children?: ReactNode;
  /* What this bar is, in one small line above whatever `children` say. Given by a wizard
     step, which has the same answer on every screen; omitted by a commit that is already
     named by the panel it closes. */
  label?: ReactNode;
  primary: ReactNode;
  /* A second command beside the primary - the PDF download beside "record the
     submission". It is not a way back (`back`) and not the one emphasized command: the
     caller draws it as a secondary button. On a phone the two share the bar's full width
     in equal halves; `secondaryIconOnly` keeps an icon button square at the start of the
     row instead, so the primary takes the rest. */
  secondary?: ReactNode;
  secondaryIconOnly?: boolean;
  /* The outcome of the command this bar owns. Keeping it inside the pinned surface means
     a result never lands outside the reader's viewport. The same node is the single live
     announcement for that result, so callers must not announce it again elsewhere. */
  result?: ReactNode;
}

/* A workflow page owns one physical action position even when the component deciding
   what belongs there lives several layers below the route. The shell supplies this
   target; a standalone CommitBar (including focused component tests) still renders in
   place. Portalling only changes layout ownership, not action ownership. */
export const CommitBarTargetContext = createContext<HTMLElement | null | undefined>(undefined);

/* The bar that closes a piece of work: the way back and what is still missing on one
   side, the command on the other.

   It replaced a disabled button with a sentence under it that only appeared once the
   reader had scrolled past everything else. Pinned to the bottom of the viewport, the
   state of the decision and the control that commits it are read together at any scroll
   position - so "why is this disabled" is answered where the button is, not above it.

   One bar for both jobs it does. A wizard step and a decision panel close the same way -
   pinned, two sides, one emphasized command - and the step needs exactly two things the
   panel does not: a way back and a name. Those are the two optional props above rather
   than a second component wrapping this one, which is what they were: a wrapper that
   passed four values through and added a heading. Each screen used to answer "what do I
   do now" in a shape of its own - a row of buttons in the flow on the preparation screen,
   a pinned approval in the editor, a download inside the identity card on the ready
   screen - and it is this component, at all three, that makes the answer one shape. */
/* The pinned bar's height, plus its 1rem offset and a little air, published as the
   page's bottom scroll padding (styles.css) for as long as the bar is mounted. */
const useScrollClearance = (pinned: boolean) => {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = ref.current;
    if (!pinned || node === null || typeof ResizeObserver === "undefined") return undefined;
    const root = document.documentElement.style;
    const observer = new ResizeObserver(() => {
      root.setProperty("--cv-commit-bar-clearance", `${Math.ceil(node.getBoundingClientRect().height) + 32}px`);
    });
    observer.observe(node);
    return () => {
      observer.disconnect();
      root.removeProperty("--cv-commit-bar-clearance");
    };
  }, [pinned]);
  return ref;
};

const CommitBarSurface = ({
  back,
  backOnPhone = true,
  children,
  inline,
  label,
  primary,
  result,
  secondary,
  secondaryIconOnly = false,
}: CommitBarProps) => {
  const ref = useScrollClearance(!inline);
  /* Whether the phone grid has a back cell. From `sm` the grid's cells are placed by the
     `sm:` classes alone, so this only ever changes the layout below the large breakpoint. */
  const phoneBack = back !== undefined && backOnPhone;
  return (
    <div
      ref={ref}
      className={cx(
        !inline && "sticky bottom-[calc(var(--cv-bottom-nav-height)+1rem)] z-(--cv-z-sticky)",
        "rounded-surface border border-cv-border bg-cv-surface/95 p-card-padding shadow-floating backdrop-blur-xl",
        /* Below the large breakpoint a pinned bar is the screen's bottom edge, as a
           phone's own action bars are: flush on the bottom navigation, edge to edge
           across the page gutter (1rem, then 1.5rem from `sm`), with a hairline above
           instead of a floating card's border, radius and shadow. */
        !inline &&
          "max-lg:bottom-(--cv-bottom-nav-height) max-lg:rounded-none max-lg:border-x-0 max-lg:border-b-0 max-lg:px-4 max-lg:py-3 max-lg:shadow-none max-sm:-mx-4 sm:max-lg:-mx-6 sm:max-lg:px-6",
      )}
    >
      {/* Two sides only where there is room for two. The action column is `max-content`, so
        on a phone it took the width of "רישום הגשת הגרסה הזו" plus "הורדת PDF" and left
        the sentence beside it about ninety pixels - one word per line, for four lines.

        Below `sm` the sentence takes the first row and the way back shares the second
        with the command. Stacked one per row - back, label, sentence, command - the
        pinned bar covered a quarter of a phone's screen over the form it closes. */}
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-3 sm:grid-cols-[minmax(0,1fr)_max-content] sm:gap-4">
        <div className="contents sm:flex sm:min-w-0 sm:flex-wrap sm:items-center sm:gap-x-5 sm:gap-y-2">
          {/* The two wrappers exist for the phone grid only; from `sm` they dissolve and
            their contents flow in the opening side's row as they always have. */}
          {back === undefined ? null : (
            <div className={cx("col-start-1 row-start-2 min-w-0 sm:contents", !backOnPhone && "max-lg:hidden")}>
              {back}
            </div>
          )}
          {label === undefined && children === undefined ? null : (
            <div className="col-span-2 min-w-0 sm:contents">
              {label === undefined ? (
                children
              ) : (
                <div className="flex min-w-0 flex-col gap-0.5">
                  {/* A phone's bar is the screen's own bottom edge and needs no name drawn
                      on it; assistive tech still hears it. */}
                  <span className="text-caption font-bold text-cv-text-muted max-lg:sr-only">{label}</span>
                  {children}
                </div>
              )}
            </div>
          )}
        </div>
        {/* On a phone the commands fill their row - each a 48px target, the label a step
            larger - so the bar reads as the screen's answer rather than a button dropped in
            a corner. The secondary comes first in the DOM, so under RTL it holds the start
            edge and the primary the closing one, on desktop as on a phone. */}
        <div
          className={cx(
            "flex flex-wrap items-center gap-3 sm:col-start-auto sm:row-start-auto sm:justify-self-end",
            phoneBack ? "col-start-2 row-start-2 justify-self-end" : "col-span-2 sm:col-span-1",
            "max-lg:flex-nowrap max-lg:gap-2 max-lg:text-body",
            !phoneBack && "max-lg:justify-self-stretch",
          )}
        >
          {secondary === undefined ? null : (
            <div
              className={cx(
                "flex",
                secondaryIconOnly ? "shrink-0 max-lg:*:size-12" : "max-lg:flex-1 max-lg:*:min-h-12 max-lg:*:flex-1",
              )}
            >
              {secondary}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3 max-lg:min-w-0 max-lg:flex-1 max-lg:flex-nowrap max-lg:*:min-h-12 max-lg:*:flex-1">
            {primary}
          </div>
        </div>
      </div>
      {result === undefined ? null : (
        <LiveRegion
          className="mt-3 border-t border-cv-border pt-3 text-support font-medium text-cv-text"
          visuallyHidden={false}
        >
          {result}
        </LiveRegion>
      )}
    </div>
  );
};

export const CommitBar = (props: CommitBarProps) => {
  const target = useContext(CommitBarTargetContext);
  const surface = <CommitBarSurface {...props} />;

  if (props.inline || target === undefined) return surface;
  if (target === null) return null;
  return createPortal(surface, target);
};
