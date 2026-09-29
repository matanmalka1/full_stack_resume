import type { ReactNode } from "react";

import { Button } from "./Button";
import { Callout } from "./Callout";

interface SuccessNoticeProps {
  children?: ReactNode;
  className?: string;
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
export const SuccessNotice = ({ children, className, onDismiss, title }: SuccessNoticeProps) => (
  <Callout
    action={
      <Button onClick={onDismiss} variant="ghost">
        סגירת ההודעה
      </Button>
    }
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
