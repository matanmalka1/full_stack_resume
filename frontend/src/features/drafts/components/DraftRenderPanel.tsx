import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { useMemo } from "react";
import { Link } from "react-router-dom";

import { operationQueryKey } from "@/api/operations";
import { approvedRevisionQueryOptions, renderApprovedRevision } from "@/api/revisions";
import { routePaths } from "@/app/routePaths";
import { CommitBar, NEXT_STEP_LABEL } from "@/features/preparation";
import { Button, buttonClasses } from "@/ui/Button";
import { ErrorCallout } from "@/ui/ErrorCallout";

interface DraftRenderPanelProps {
  approvedRevisionId: string;
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

/* A.4 frame 6's render step, inline in the editor that produced the revision.
   Rendering stays an explicit action with its own retry: it queues a durable Operation
   and it can fail on its own, and a render that fired itself on approval would queue
   work the user never asked for and leave a failure with nothing that asked for it.
   Approval is what became one click; rendering is one more, in place. */
export const DraftRenderPanel = ({ approvedRevisionId, onQueued }: DraftRenderPanelProps) => {
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
