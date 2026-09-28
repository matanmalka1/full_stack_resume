import { ArrowRight, LoaderCircle } from "lucide-react";
import { Link } from "react-router-dom";

import { routePaths } from "@/app/routePaths";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { CommitBar, NEXT_STEP_LABEL } from "@/ui/CommitBar";
import { ErrorCallout } from "@/ui/ErrorCallout";
import type { RenderDocument } from "../hooks/useRenderDocument";

/* A.4 frame 6's render step, inline in the editor. Explicit approval starts it; a failed
   Operation remains in the editor's overlay with its retry, while reloading an approved
   document does not create new work.

   The document stays editable beside this panel: editing an approved document is allowed
   and simply returns it to draft (§14). A failed render leaves it approved (§16), and the
   projection's `last_render_error` says why until the next render or edit. */
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

  /* While the render runs, the screen still says where the work stands. It offers nothing
     to press - the run is the live panel's to report and cancel. */
  if (inFlight) {
    return (
      <section
        aria-labelledby="render-heading"
        className="flex items-start gap-3 rounded-surface border-2 border-cv-success/30 bg-cv-success-soft p-5"
      >
        <LoaderCircle
          aria-hidden="true"
          className="mt-1 size-icon-md shrink-0 text-cv-accent motion-safe:animate-spin"
        />
        <div>
          <h2 className="text-heading-sm font-bold text-cv-text" id="render-heading">
            הגרסה אושרה
          </h2>
          <p className="mt-1 text-support leading-6 text-cv-text-muted">
            יוצרים ממנה HTML ו־PDF. כשהקבצים יהיו מוכנים, המסך יעבור לקורות החיים המוכנים למסירה.
          </p>
        </div>
      </section>
    );
  }

  const failureDetail =
    lastRenderError == null
      ? null
      : typeof lastRenderError.detail === "string"
        ? lastRenderError.detail
        : typeof lastRenderError.code === "string"
          ? lastRenderError.code
          : null;

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
            {failureDetail === null ? (
              "המסמך נשאר מאושר. אפשר לנסות שוב, או לתקן את התוכן - עריכה תחזיר אותו לטיוטה."
            ) : (
              <p dir="auto">{failureDetail}</p>
            )}
          </Callout>
        )}

        {render.error === null ? null : (
          <ErrorCallout
            error={render.error}
            fallbackDetail="הפנייה לשרת נכשלה. המסמך נשאר מאושר."
            fallbackTitle="לא ניתן להתחיל את יצירת הקובץ"
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
