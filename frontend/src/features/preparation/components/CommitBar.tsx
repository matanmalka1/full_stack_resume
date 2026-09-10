import { Circle, CircleCheck } from "lucide-react";
import { createContext, useContext, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { cx } from "@/ui/cx";
import { LiveRegion } from "@/ui/LiveRegion";

/* What every pinned bar in the flow calls itself when it is a wizard step's action rather
   than a form's commit. Named "מה עושים עכשיו" and not "הצעד הבא": the bar carries the
   action the current step is waiting on, not the step after it, and the board already
   spends "הצעד הבא" on a recruitment reminder that has nothing to do with the CV work. */
export const NEXT_STEP_LABEL = "מה עושים עכשיו";

interface CommitBarProps {
  /* The way back to the previous step, ahead of everything else on the opening edge. A
     wizard that only goes forward is a form; what makes the spine navigable in both
     directions has to be true of the bar as well.

     Absent on a bar that commits a decision rather than closing a step, and absent on the
     first step with a record - the intake behind it created the Application, and
     re-entering it would not be going back. */
  back?: ReactNode;
  children?: ReactNode;
  /* What this bar is, in one small line above whatever `children` say. Given by a wizard
     step, which has the same answer on every screen; omitted by a commit that is already
     named by the panel it closes. */
  label?: ReactNode;
  primary: ReactNode;
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
const CommitBarSurface = ({ back, children, label, primary, result }: CommitBarProps) => (
  <div className="sticky bottom-4 z-(--cv-z-sticky) rounded-surface border border-cv-border bg-cv-surface/95 p-card-padding shadow-floating backdrop-blur-xl">
    <div className="grid grid-cols-[minmax(0,1fr)_max-content] items-center gap-4">
      <div className="flex min-w-0 flex-wrap items-center gap-x-5 gap-y-2">
        {back}
        {label === undefined ? (
          children
        ) : (
          <div className="flex min-w-0 flex-col gap-0.5">
            <span className="text-caption font-bold text-cv-text-muted">{label}</span>
            {children}
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center justify-self-end gap-3">{primary}</div>
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

export const CommitBar = (props: CommitBarProps) => {
  const target = useContext(CommitBarTargetContext);
  const surface = <CommitBarSurface {...props} />;

  if (target === undefined) return surface;
  if (target === null) return null;
  return createPortal(surface, target);
};

export interface ChecklistEntry {
  done: boolean;
  label: string;
}

/* The live checklist. Colour is never the only signal (A.2): a done entry changes its
   mark from a ring to a ring with a tick, and states which it is in words for a reader
   who hears the list rather than sees it. */
export const CommitChecklist = ({ entries, label }: { entries: readonly ChecklistEntry[]; label: string }) => (
  <ul aria-label={label} className="flex flex-wrap items-center gap-x-5 gap-y-2">
    {entries.map((entry) => (
      <li className="flex items-center gap-2 text-support font-medium" key={entry.label}>
        {entry.done ? (
          <CircleCheck aria-hidden="true" className="size-icon-md shrink-0 text-cv-success" />
        ) : (
          <Circle aria-hidden="true" className="size-icon-md shrink-0 text-cv-text-muted" />
        )}
        <span className={cx(entry.done ? "text-cv-text" : "text-cv-text-muted")}>{entry.label}</span>
        <span className="sr-only">{entry.done ? "הושלם" : "טרם הושלם"}</span>
      </li>
    ))}
  </ul>
);
