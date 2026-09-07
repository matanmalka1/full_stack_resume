import type { ApplicationDetail } from "@/api/contracts";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { Disclosure } from "@/ui/Disclosure";
import { resolvedByReviewDecision } from "../model/reviewDecisions";
import { actionLabel, blockedReasonLabel, warningTitle } from "../model/preparationLabels";
import { ReasonCallout } from "./ReasonCallout";
import { actionIsOnPreparationScreen } from "../model/actionDestinations";

/* One alert backdrop with a fixed severity/order: failed automatic start, review
   blockers, stale sources, general warnings, then the informational newer-draft note.
   Keeping this region visually quiet lets the action surface beside it remain the clear
   place to continue the workflow. */
export const PreparationAlerts = ({ detail }: { detail: ApplicationDetail }) => {
  /* A reason resolved by the decision form is presented with its control instead of
     once here as an alert and once again below as a decision. Reasons owned elsewhere
     keep their callout and resolution route. */
  const reviewReasons = detail.review_reasons.filter((reason) => !resolvedByReviewDecision(reason));
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
          fallbackTitle="נדרשת החלטה לפני המשך"
          key={reason.code}
          reason={reason}
          resolvedHere={
            resolvedByReviewDecision(reason) || reason.allowed_resolution_actions.includes("create_selection_plan")
          }
          tone="blocker"
        />
      ))}

      {detail.stale_reasons.map((reason) => (
        <ReasonCallout
          applicationId={detail.application.id}
          fallbackTitle="הטיוטה אינה מעודכנת מול המקורות שלה"
          key={reason.code}
          reason={reason}
          resolvedHere={reason.allowed_resolution_actions.some((action) =>
            actionIsOnPreparationScreen(action, detail.application.id),
          )}
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
