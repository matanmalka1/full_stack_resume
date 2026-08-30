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
  /* The surface exists to group a row of choices and separate it from the content above.
     With a single action there is no row and nothing to separate: the panel became a
     bordered box holding one button, which reads as an empty region with a control
     dropped into it rather than as the page's next step. So the chrome follows the
     secondaries - the bar is a bar when it has sides, and a plain control otherwise. */
  const grouped = secondary !== undefined;

  return (
    <div
      className={cx(
        "flex flex-wrap items-center gap-3",
        grouped
          ? "mt-8 justify-between rounded-surface border border-cv-border bg-cv-surface-muted p-4 shadow-inner"
          : align === "start"
            ? "justify-start"
            : "justify-end",
        className,
      )}
    >
      {secondary === undefined ? null : <div className="flex flex-wrap gap-3">{secondary}</div>}
      <div className="flex flex-wrap gap-3">{primary}</div>
    </div>
  );
};
