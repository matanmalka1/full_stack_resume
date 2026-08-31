import { Link } from "react-router-dom";

import type { Reason } from "../../api/contracts";
import { buttonClasses } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { actionDestination } from "./actionDestinations";
import { actionLabel, reasonTitle } from "./applicationLabels";

/* Review reasons and stale reasons carry the same shape, and both are reported as a
   short title plus the control that resolves them.

   The backend's `message` is not rendered. It is a complete explanatory sentence, and up
   to five of them stacked on this screen at once was the wall this screen opened with.
   The code maps to a title instead, and the action that clears it is a control rather
   than another sentence naming a control. */
export const ReasonCallout = ({
  applicationId,
  fallbackTitle,
  reason,
  resolvedHere = false,
  tone,
}: {
  applicationId: string;
  fallbackTitle: string;
  reason: Reason;
  /* The control that resolves this reason is on this screen, so the callout states the
     requirement and offers no destination. */
  resolvedHere?: boolean;
  tone: "blocker" | "warning";
}) => {
  const resolution = resolvedHere
    ? undefined
    : reason.allowed_resolution_actions
        .map((action) => ({ action, href: actionDestination(action, applicationId) }))
        .find((candidate) => candidate.href !== null);

  return (
    <Callout
      action={
        resolution?.href == null ? undefined : (
          <Link className={buttonClasses("secondary")} to={resolution.href}>
            {actionLabel(resolution.action)}
          </Link>
        )
      }
      title={reasonTitle(reason.code, fallbackTitle)}
      tone={tone}
    />
  );
};
