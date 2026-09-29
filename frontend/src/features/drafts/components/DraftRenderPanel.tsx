import { ArrowRight } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";

import { routePaths } from "@/app/routePaths";
import { recordedFailureDetail } from "@/features/operations";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { CommitBar, NEXT_STEP_LABEL } from "@/ui/CommitBar";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { reportError } from "@/ui/reportError";
import type { RenderDocument } from "../hooks/useRenderDocument";

/* A.4 frame 6's render step, inline in the editor. Explicit approval starts it; a failed
   Operation remains in the editor's overlay with its retry, while reloading an approved
   document does not create new work.

   The document stays editable beside this panel: editing an approved document is allowed
   and simply returns it to draft (§14). A failed render leaves it approved (§16), and the
   projection's `last_render_error` records why until the next render or edit. Its
   structured reason is worded the way the Operation report words it; its English detail
   is diagnostic and goes to the console. */
export const DraftRenderPanel = ({
  applicationId,
  lastRenderError,
  state,
}: {
  applicationId: string;
  /* §9: the structured failure of the newest failed render of this exact document. */
  lastRenderError: Record<string, unknown> | null | undefined;
  state: RenderDocument;
}) => {
  const { inFlight, ready, render } = state;
  useEffect(() => {
    if (lastRenderError != null) reportError("render_failure", lastRenderError);
  }, [lastRenderError]);
  const failureDetail = recordedFailureDetail(lastRenderError);

  /* While the render runs the editor's Operation panel stands here, inline: it is the
     one account of the run, with its phase and its report. This panel used to draw a
     banner of its own beside it, so the same wait was shown twice. */
  if (inFlight) return null;

  return (
    <>
      <section
        aria-labelledby="render-heading"
        className="flex flex-col gap-4 rounded-surface border-2 border-cv-success/30 bg-cv-success-soft p-5"
      >
        <div>
          <h2 className="text-heading-sm font-bold text-cv-text" id="render-heading">
            {ready ? "קורות החיים מוכנים" : "הגרסה אושרה"}
          </h2>
          <p className="mt-1 text-support leading-6 text-cv-text-muted">
            {ready
              ? "הקבצים נוצרו מהמסמך כפי שהוא. עריכה כאן תחזיר אותו לטיוטה, ואפשר לאשר ולהפיק אותו שוב."
              : "המסמך אושר כפי שהוא. כעת נותר ליצור ממנו HTML ו־PDF. עריכה תחזיר אותו לטיוטה."}
          </p>
        </div>

        {lastRenderError == null ? null : (
          <Callout title="יצירת הקובץ האחרונה נכשלה" tone="blocker">
            {failureDetail === null ? null : <p className="font-medium">{failureDetail}</p>}
            <p>המסמך נשאר מאושר. אפשר לנסות שוב, או לתקן את התוכן - עריכה תחזיר אותו לטיוטה.</p>
          </Callout>
        )}

        {render.error === null ? null : (
          <ErrorCallout
            error={render.error}
            fallbackDetail="המסמך נשאר מאושר. אפשר לנסות שוב."
            title="יצירת הקבצים לא התחילה"
          />
        )}
      </section>

      <CommitBar
        back={
          <Link className={buttonClasses("ghost")} to={routePaths.application(applicationId)}>
            <ArrowRight aria-hidden="true" className="size-icon-md" />
            חזרה לניתוח והתאמה
          </Link>
        }
        label={NEXT_STEP_LABEL}
        primary={
          ready ? (
            <Link className={buttonClasses("primary")} to={routePaths.ready(applicationId)}>
              מעבר לקורות החיים המוכנים
            </Link>
          ) : (
            <Button onClick={() => render.mutate()} pending={render.isPending} pendingLabel="יוצר HTML ו־PDF…">
              יצירת HTML ו־PDF
            </Button>
          )
        }
      >
        <p className="text-support leading-6 text-cv-text-muted">
          {ready ? "שלב הטיוטה הושלם." : "האישור הושלם; יצירת הקבצים היא הפעולה האחרונה בשלב הזה."}
        </p>
      </CommitBar>
    </>
  );
};
