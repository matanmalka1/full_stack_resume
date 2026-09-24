import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { routePaths } from "@/app/routePaths";
import { Button, buttonClasses } from "@/ui/Button";
import { CommitBar, NEXT_STEP_LABEL } from "@/ui/CommitBar";
import { ErrorCallout } from "@/ui/ErrorCallout";
import type { RenderApprovedRevision } from "../hooks/useRenderApprovedRevision";

/* A.4 frame 6's render step, inline in the editor that produced the revision. Explicit
   approval starts its artifact generation; a failed Operation remains in the editor's
   overlay with its retry and direct return to editing, while reloading an already-approved
   revision does not create new work.

   The command itself is the editor's (`useRenderApprovedRevision`), because the editor's
   one overlay reports the render from the press onward. This panel draws the approved
   state and its manual start, and steps aside while the render is anyone's to report:
   the approved box and its "create the files" CTA beside a render already under way, or
   already failed with its own recovery actions, would be a second, contradictory account
   of the same moment. */
export const DraftRenderPanel = ({ state }: { state: RenderApprovedRevision }) => {
  const { inFlight, ready, render, revision, revisionError } = state;

  if (inFlight) return null;

  return (
    <>
      <section
        aria-labelledby="render-heading"
        className="flex flex-col gap-4 rounded-surface border-2 border-cv-success/30 bg-cv-success-soft p-5"
      >
        <div>
          <h2 className="text-heading-sm font-bold text-cv-text" id="render-heading">
            הגרסה אושרה
          </h2>
          <p className="mt-1 text-support leading-6 text-cv-text-muted">
            {ready
              ? "הקבצים נוצרו בהצלחה. אפשר להמשיך לגרסה המוכנה למסירה."
              : "הגרסה שאושרה נשמרה כרשומה קבועה. כעת נותר ליצור ממנה HTML ו־PDF."}
          </p>
        </div>

        {revisionError === null && render.error === null ? null : (
          <ErrorCallout
            error={render.error ?? revisionError}
            fallbackDetail="הפנייה לשרת נכשלה. הגרסה המאושרת נשמרה."
            fallbackTitle="לא ניתן להתחיל את יצירת הקובץ"
          />
        )}
      </section>

      <CommitBar
        back={
          revision === undefined ? undefined : (
            <Link className={buttonClasses("ghost")} to={routePaths.application(revision.application_id)}>
              <ArrowRight aria-hidden="true" className="size-icon-md" />
              חזרה לניתוח והתאמה
            </Link>
          )
        }
        label={NEXT_STEP_LABEL}
        primary={
          revision?.ready_qualified === true ? (
            <Link className={buttonClasses("primary")} to={routePaths.revision(revision.id)}>
              מעבר לגרסה המוכנה
            </Link>
          ) : (
            <Button
              disabled={revision === undefined}
              onClick={() => render.mutate()}
              pending={render.isPending}
              pendingLabel="יוצר HTML ו־PDF…"
            >
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
