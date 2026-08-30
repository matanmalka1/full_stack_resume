import type { ReactNode } from "react";

import { cx } from "./cx";

interface ActionBarProps {
  /* Where a lone action sits. A bar closing a form belongs at the end, the way a submit
     always has; an action continuing a sentence belongs where the reading starts. Only
     the caller knows which it is, so it is asked rather than inferred, and the default is
     the closing-edge behaviour every existing caller was written against. With secondary
     actions the bar has two sides and this does not apply. */
  align?: "start" | "end";
  className?: string;
  /* A.1: one emphasized primary action per page. */
  primary: ReactNode;
  secondary?: ReactNode;
}

export const ActionBar = ({
  align = "end",
  className,
  primary,
  secondary,
}: ActionBarProps) => {
  /* The panel is the chrome of a bar with two sides: it exists to span the width and hold
     a primary and a way out at opposite edges, and the border is what makes that span read
     as one region rather than two stranded buttons.

     So it follows the span, not the button count. A single action does not span anything,
     and neither does a group sitting together at the start - both left the border drawn
     around mostly empty surface, which reads as an empty region with controls dropped into
     a corner of it. Either of those is a plain row of controls; only the split bar is a
     bar. */
  const split = secondary !== undefined && align === "end";
  /* Split, the secondaries come first so the primary lands on the closing edge. Anywhere
     else the actions sit together and that order would hand the leading position to the
     lesser action, so the primary is emitted first instead. This is a DOM reorder rather
     than `flex-row-reverse`: the shell is RTL, so the row already runs right-to-left, and
     reversing it would flip the group to the wrong edge as well as reorder it. */
  const primaryLeads = !split && secondary !== undefined;

  return (
    <div
      className={cx(
        "flex flex-wrap items-center gap-3",
        split
          ? "mt-8 justify-between rounded-surface border border-cv-border bg-cv-surface-muted p-4 shadow-inner"
          : align === "start"
            ? "justify-start"
            : "justify-end",
        className,
      )}
    >
      {primaryLeads ? <div className="flex flex-wrap gap-3">{primary}</div> : null}
      {secondary === undefined ? null : <div className="flex flex-wrap gap-3">{secondary}</div>}
      {primaryLeads ? null : <div className="flex flex-wrap gap-3">{primary}</div>}
    </div>
  );
};
