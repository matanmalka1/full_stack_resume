import { type ReactNode, useEffect } from "react";

import { Callout } from "./Callout";
import { fieldIssueLine, problemDetailsFrom, problemFieldErrors, problemMessage } from "./errorMessages";
import { reportError } from "./reportError";

interface ErrorCalloutProps {
  /* The way out, when the screen has one - "ניסיון חוזר", a link back. */
  action?: ReactNode;
  className?: string;
  error: unknown;
  /* What the screen can say when the failure's code is unknown or it is a local error:
     what stayed as it was, and whether trying again makes sense. */
  fallbackDetail?: string;
  /* Server field names the form already shows under their own controls. */
  inlineFields?: ReadonlySet<string>;
  /* What did not happen, in the screen's own words: "ההגדרות לא נשמרו". */
  title: string;
}

const defaultFallbackDetail = "הפעולה לא הושלמה. אפשר לרענן את העמוד ולנסות שוב.";

/** The one presentation for a failed API query or command.

    Placement is the caller's, by one rule: a failure of a whole region replaces or tops
    that region (`QueryState`); a failure of a command sits directly under the control
    row that sent it, or at the end of its form, above the submit button.

    The title is always the screen's - it names what did not happen. The body is the
    catalogue's reason and action for a known code, or the screen's fallback detail.
    Server prose, codes and exception text never reach the page; `reportError` keeps
    them in the console. Field refusals that the form shows under their own fields are
    left out; any it could not place are listed here. */
export const ErrorCallout = ({
  action,
  className,
  error,
  fallbackDetail = defaultFallbackDetail,
  inlineFields,
  title,
}: ErrorCalloutProps) => {
  useEffect(() => {
    reportError("ui_error", error);
  }, [error]);

  const problem = problemDetailsFrom(error);
  const message = problem === null ? null : problemMessage(problem);
  const listed = [...problemFieldErrors(error)].filter(([field]) => inlineFields?.has(field) !== true);
  const body =
    message === null ? fallbackDetail : listed.length === 0 ? `${message.reason} ${message.action}` : message.reason;

  return (
    <Callout action={action} className={className} role="alert" title={title} tone="blocker">
      <p>{body}</p>
      {listed.length === 0 ? null : (
        <>
          <ul className="mt-1 list-disc space-y-1 ps-5">
            {listed.map(([field, issue]) => (
              <li key={field}>{fieldIssueLine(field, issue)}</li>
            ))}
          </ul>
          <p className="mt-1">יש לתקן את הערכים ולנסות שוב.</p>
        </>
      )}
    </Callout>
  );
};
