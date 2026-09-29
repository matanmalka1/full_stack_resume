import type { ReactNode } from "react";

import { Button } from "./Button";
import { Callout } from "./Callout";
import { cx } from "./cx";

interface SuccessNoticeProps {
  children?: ReactNode;
  className?: string;
  /* "milestone" is for the one success a whole flow ends on - recording the submission
     the CV was prepared for. Every other success stays the quiet inline notice: a flow
     that celebrated each save would have nothing left to mark its end with. */
  emphasis?: "milestone";
  onDismiss: () => void;
  title: string;
}

/** The one shape of a success message, and the bar for having one at all.

    A command earns a success notice only when the reader learns something the screen
    does not already show: a consequence ("the analysis is no longer current"), a record
    that now exists elsewhere, or a result that has no other place on the page. A command
    whose effect is visible where it happened - a row that changed, a button that became
    disabled - says nothing.

    It appears after the server confirmed, never optimistically; it is announced politely
    and never takes focus; and it stays until the reader closes it, starts another
    command, or the screen moves past what it describes. It never times out, so nobody
    has to read it against a clock. */
export const SuccessNotice = ({ children, className, emphasis, onDismiss, title }: SuccessNoticeProps) => {
  const dismiss = (
    <Button onClick={onDismiss} variant="ghost">
      סגירת ההודעה
    </Button>
  );

  if (emphasis === "milestone") {
    return (
      /* A card rather than an edge-marked line, with a filled mark whose tick draws in
         (styles.css, `cv-success-mark`). Monochrome like every other state: what makes it
         read as the end of the flow is its weight, its mark and its place at the top of
         the step, not a colour the rest of the interface never uses. */
      <output
        className={cx(
          "flex flex-col items-start gap-4 rounded-surface border border-cv-border bg-cv-surface p-5 shadow-surface sm:flex-row sm:items-center",
          className,
        )}
      >
        <span
          aria-hidden="true"
          className="cv-success-mark flex size-12 shrink-0 items-center justify-center rounded-pill bg-cv-accent text-cv-on-accent"
        >
          <svg
            className="size-6"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={3}
            viewBox="0 0 24 24"
          >
            <path d="M5 12.5l4.5 4.5L19 7.5" />
          </svg>
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-heading-sm font-bold text-cv-text">{title}</p>
          {children === undefined ? null : (
            <div className="mt-1 text-support leading-6 text-cv-text-muted" dir="auto">
              {children}
            </div>
          )}
        </div>
        <div className="shrink-0">{dismiss}</div>
      </output>
    );
  }

  return (
    <Callout
      action={dismiss}
      className={className}
      // role="status" is a Callout prop, not a DOM role; Callout already renders an
      // <output> for it.
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      role="status"
      title={title}
      tone="success"
    >
      {children}
    </Callout>
  );
};
