import { Link } from "react-router-dom";

import type { ApplicationDetail, Reason } from "@/api/contracts";
import { buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { Disclosure } from "@/ui/Disclosure";
import { type PreparationScreen, actionDestination, screenPath } from "../../model/actionDestinations";
import { actionLabel, blockedReasonLabel, reasonTitle, warningTitle } from "../../model/preparationLabels";
import { resolvedByReviewDecision } from "../../model/reviewDecisions";

/* Review reasons and stale reasons carry the same shape, and both are reported as a
   short title plus the control that resolves them. The server's complete message stays
   available behind a disclosure: it is useful evidence when a reader needs it, but does
   not turn several simultaneous reasons into the wall of text this screen used to open
   with. The internal code remains translated rather than exposed as UI vocabulary. */
const ReasonCallout = ({
  applicationId,
  currentPath,
  fallbackTitle,
  reason,
  tone,
}: {
  applicationId: string;
  /* Where the reader is standing. A resolution that lands back here is not offered: the
     control is already on the screen, and a link to it would be a link to the page the
     reader is reading. A resolution anywhere else is always offered - that is the whole
     point of showing the reason on a screen that cannot answer it. */
  currentPath: string;
  fallbackTitle: string;
  reason: Reason;
  tone: "blocker" | "warning";
}) => {
  const resolution = reason.allowed_resolution_actions
    .map((action) => ({ action, href: actionDestination(action, applicationId) }))
    .find((candidate) => candidate.href !== null && candidate.href !== currentPath);

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

/* One alert backdrop with a fixed severity/order: failed automatic start, review
   blockers, stale sources, general warnings, then the informational newer-draft note.
   Keeping this region visually quiet lets the action surface beside it remain the clear
   place to continue the workflow. */
export const PreparationAlerts = ({
  detail,
  screen = "preparation",
}: {
  detail: ApplicationDetail;
  /* Which screen is rendering the region. The preparation screen carries the decision
     form, so a reason that form answers is left to it; the draft editor carries none, so
     the same reason is stated there with the way back to the control that resolves it.
     The editor used to render its own two `map`s over the same arrays - title only, no
     server message, no resolution - which turned every blocker into a dead end on the one
     screen where approval is refused. */
  screen?: PreparationScreen;
}) => {
  const currentPath = screenPath(screen, detail.application.id);
  /* A reason resolved by the decision form is presented with its control instead of
     once here as an alert and once again below as a decision - but only where that form
     is actually rendered. */
  const reviewReasons = detail.review_reasons.filter(
    (reason) => !(screen === "preparation" && resolvedByReviewDecision(reason)),
  );
  const statedReasonCodes = new Set([...detail.review_reasons, ...detail.stale_reasons].map((reason) => reason.code));
  /* `blocked_actions` contains the normal future workflow as well as exceptional
     blockers. Only translated exceptions are useful here, and a reason already stated
     by its own callout is not repeated once for every action it blocks. The translation
     table is therefore the deliberate exception list: a new backend reason stays quiet
     until the UI has an intentional sentence for it. */
  const exceptionalBlockedActions = detail.blocked_actions.flatMap((blocked) => {
    const reasons = blocked.reasons.flatMap((reason) => {
      if (statedReasonCodes.has(reason)) {
        return [];
      }
      const label = blockedReasonLabel(reason);
      return label === null ? [] : [label];
    });
    return reasons.length === 0 ? [] : [{ action: blocked.action, reasons: [...new Set(reasons)] }];
  });
  const hasAlerts =
    reviewReasons.length > 0 ||
    detail.stale_reasons.length > 0 ||
    detail.warnings.length > 0 ||
    exceptionalBlockedActions.length > 0 ||
    detail.newer_draft_in_progress;

  if (!hasAlerts) {
    return null;
  }

  return (
    <Card aria-label="התראות" className="flex flex-col gap-3 bg-cv-surface-muted p-3">
      {/* A review reason whose control is in the decision panel states the requirement
          and stops there. Other reasons retain the action that resolves them. */}
      {reviewReasons.map((reason) => (
        <ReasonCallout
          applicationId={detail.application.id}
          currentPath={currentPath}
          fallbackTitle="נדרשת החלטה לפני המשך"
          key={reason.code}
          reason={reason}
          tone="blocker"
        />
      ))}

      {detail.stale_reasons.map((reason) => (
        <ReasonCallout
          applicationId={detail.application.id}
          currentPath={currentPath}
          fallbackTitle="הטיוטה אינה מעודכנת מול המקורות שלה"
          key={reason.code}
          reason={reason}
          tone="warning"
        />
      ))}

      {detail.warnings.map((warning) => (
        <Callout key={warning.code} title={warningTitle(warning.code)} tone="warning">
          <Disclosure summary="פרטי האזהרה">
            <p dir="auto">{warning.message}</p>
          </Disclosure>
        </Callout>
      ))}

      {exceptionalBlockedActions.map((blocked) => (
        <Callout key={blocked.action} title={`הפעולה ${actionLabel(blocked.action)} חסומה כרגע`} tone="blocker">
          <ul className="flex list-disc flex-col gap-1 ps-5">
            {blocked.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </Callout>
      ))}

      {detail.newer_draft_in_progress ? (
        <Callout title="קיימת טיוטה חדשה יותר מהגרסה שאושרה" tone="warning">
          הגרסה שאושרה נשמרת בדיוק כפי שהיא. הטיוטה החדשה היא עבודה נפרדת ואינה משנה אותה.
        </Callout>
      ) : null}
    </Card>
  );
};
