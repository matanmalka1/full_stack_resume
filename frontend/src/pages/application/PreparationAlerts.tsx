import type { ApplicationDetail } from "../../api/contracts";
import { Callout } from "../../ui/Callout";
import { resolvedByDecisionForm } from "./ReviewDecisionPanel";
import { warningTitle } from "./applicationLabels";
import { ReasonCallout } from "./ReasonCallout";

/* One alert backdrop with a fixed severity/order: failed automatic start, review
   blockers, stale sources, general warnings, then the informational newer-draft note.
   Keeping this region visually quiet lets the action surface beside it remain the clear
   place to continue the workflow. */
export const PreparationAlerts = ({
  automaticAnalysisStartFailed,
  detail,
}: {
  automaticAnalysisStartFailed: boolean;
  detail: ApplicationDetail;
}) => {
  const showAutomaticFailure =
    automaticAnalysisStartFailed &&
    detail.preparation_state === "needs_analysis" &&
    detail.active_operation == null;
  const hasAlerts =
    showAutomaticFailure ||
    detail.review_reasons.length > 0 ||
    detail.stale_reasons.length > 0 ||
    detail.warnings.length > 0 ||
    detail.newer_draft_in_progress;

  if (!hasAlerts) {
    return null;
  }

  return (
    <section
      aria-label="התראות"
      className="flex flex-col gap-3 rounded-surface border border-cv-border bg-cv-surface-muted p-3"
    >
      {showAutomaticFailure ? (
        <Callout title="המועמדות נוצרה, אך הניתוח לא הופעל" tone="warning">
          ניתן להפעיל את ניתוח המשרה מהפעולה שלמטה. יצירת המועמדות לא תבוצע שוב.
        </Callout>
      ) : null}

      {/* A review reason whose control is in the decision panel states the requirement
          and stops there. Other reasons retain the action that resolves them. */}
      {detail.review_reasons.map((reason) => (
        <ReasonCallout
          applicationId={detail.application.id}
          fallbackTitle="נדרשת החלטה לפני המשך"
          key={reason.code}
          reason={reason}
          resolvedHere={resolvedByDecisionForm(reason)}
          tone="blocker"
        />
      ))}

      {detail.stale_reasons.map((reason) => (
        <ReasonCallout
          applicationId={detail.application.id}
          fallbackTitle="הטיוטה אינה מעודכנת מול המקורות שלה"
          key={reason.code}
          reason={reason}
          tone="warning"
        />
      ))}

      {detail.warnings.map((warning) => (
        <Callout key={warning.code} title={warningTitle(warning.code)} tone="warning" />
      ))}

      {detail.newer_draft_in_progress ? (
        <Callout title="קיימת טיוטה חדשה יותר מהגרסה שאושרה" tone="warning">
          הגרסה שאושרה נשמרת בדיוק כפי שהיא. הטיוטה החדשה היא עבודה נפרדת ואינה משנה אותה.
        </Callout>
      ) : null}
    </section>
  );
};
