import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { Link } from "react-router-dom";

import { operationQueryKey } from "@/api/operations";
import { approvedRevisionQueryOptions, renderApprovedRevision } from "@/api/revisions";
import { routePaths } from "@/app/routePaths";
import { CommitBar, NEXT_STEP_LABEL } from "@/features/preparation";
import { Button, buttonClasses } from "@/ui/Button";
import { ErrorCallout } from "@/ui/ErrorCallout";

interface DraftRenderPanelProps {
  approvedRevisionId: string;
  /* True only in the render reached by this screen's just-completed approval. Reloading
     an older approved state remains passive, so a visit never queues artifact work by
     itself. */
  autoStart?: boolean;
  /* Whether a render Operation for this revision is queued or running right now, read from
     the same watched Operation the host screen shows in `ActiveOperationPanel`. That panel
     is the single live status of the render; while it is up, this panel must not also offer
     a "create the files" button - the file creation is already under way, so the approved
     box and its CTA are a second, contradictory account of the same moment. */
  rendering?: boolean;
  /* What this panel just queued, handed to the editor that holds it. Rendering used to
     navigate to the Operation's own screen, which took the approved draft off the display
     at the moment the user was waiting to see what became of it - and the way back from
     there led to the Application screen rather than to the editor, so the file that had
     just been produced was never linked from the screen that produced it.

     The editor already watches this Application's work, so the accepted `202` goes to
     that watch instead. The `202` is the earliest and most certain answer: the projection
     reports an Operation only on its next read. */
  onQueued: (operationId: string) => void;
}

/* A.4 frame 6's render step, inline in the editor that produced the revision. Explicit
   approval starts its artifact generation; a failed Operation remains here with the same
   manual retry, while reloading an already-approved revision does not create new work. */
export const DraftRenderPanel = ({
  approvedRevisionId,
  autoStart = false,
  onQueued,
  rendering = false,
}: DraftRenderPanelProps) => {
  const queryClient = useQueryClient();
  const revisionQuery = useQuery(approvedRevisionQueryOptions(approvedRevisionId));
  const revision = revisionQuery.data;
  const renderKey = useMemo(() => `render:${approvedRevisionId}`, [approvedRevisionId]);

  const render = useMutation({
    mutationFn: async () => {
      if (revision === undefined) throw new Error("Render was offered before the revision loaded");
      return renderApprovedRevision(revision.id, revision.application_id, renderKey);
    },
    onSuccess: ({ operation }) => {
      queryClient.setQueryData(operationQueryKey(operation.id), operation);
      onQueued(operation.id);
    },
  });

  const ready = revision?.ready_qualified === true;
  const automaticAttempted = useRef(false);
  useEffect(() => {
    if (!autoStart || automaticAttempted.current || revision === undefined || ready) return;
    automaticAttempted.current = true;
    render.mutate();
  }, [autoStart, ready, render, revision]);

  /* While the render is under way, this panel steps aside for the one that is actually
     reporting it. `ActiveOperationPanel` shows the live status and owns cancel and retry;
     a failed run stays there with its retry, so this panel does not offer a second one.

     `render.isPending` covers the moment before the accepted 202 has named an Operation to
     watch, and the auto-start branch covers the same window in the automatic path: with
     `autoStart` set the render always begins on mount, so the approved box and its manual
     CTA are never the right thing to show. The one auto case that does belong here is a 202
     that never queued anything (`render.error`), which leaves no Operation for the other
     panel to report - then the retry below is the only way on. */
  const renderInFlight = rendering || render.isPending || (autoStart && !ready && render.error === null);
  if (renderInFlight) {
    return null;
  }

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

        {revisionQuery.error === null && render.error === null ? null : (
          <ErrorCallout
            error={render.error ?? revisionQuery.error}
            fallbackDetail="הפנייה לשרת נכשלה. הגרסה המאושרת נשמרה."
            fallbackTitle="לא ניתן להתחיל את יצירת הקובץ"
          />
        )}
      </section>

      <CommitBar
        back={
          revision === undefined ? undefined : (
            <Link className={buttonClasses("ghost")} to={routePaths.application(revision.application_id)}>
              <ArrowRight aria-hidden="true" className="size-4" />
              חזרה לניתוח ולהתאמה
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
