import { Link } from "react-router-dom";

import type { Reason } from "../../api/contracts";
import { buttonClasses } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Disclosure } from "../../ui/Disclosure";
import { actionDestination } from "./actionDestinations";
import { actionLabel, reasonTitle } from "./applicationLabels";

/* Review reasons and stale reasons carry the same shape, and both are reported as a
   short title plus the control that resolves them. The server's complete message stays
   available behind a disclosure: it is useful evidence when a reader needs it, but does
   not turn several simultaneous reasons into the wall of text this screen used to open
   with. The internal code remains translated rather than exposed as UI vocabulary. */
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
    >
      <Disclosure summary="פרטי הסיבה">
        <p dir="auto">{reason.message}</p>
      </Disclosure>
    </Callout>
  );
};
