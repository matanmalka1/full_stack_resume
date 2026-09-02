import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link } from "react-router-dom";

import { operationQueryKey } from "../../api/operations";
import { approvedRevisionQueryOptions, renderApprovedRevision } from "../../api/revisions";
import { ErrorCallout } from "../../app/ErrorCallout";
import { appRoutes } from "../../app/appRoutes";
import { Button, buttonClasses } from "../../ui/Button";

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

  return (
    <section
      aria-labelledby="render-heading"
      className="flex flex-col gap-4 rounded-surface border-2 border-cv-success/30 bg-cv-success-soft p-5"
    >
      <div>
        <h2 className="text-heading-sm font-bold text-cv-text" id="render-heading">
          הגרסה אושרה
        </h2>
        <p className="mt-1 text-support leading-6 text-cv-text-muted">
          הגרסה שאושרה נשמרה כרשומה קבועה. יצירת הקובץ היא פעולה נפרדת, והגרסה נשארת מאושרת גם אם היא נכשלת.
        </p>
      </div>

      {revisionQuery.error === null && render.error === null ? null : (
        <ErrorCallout
          error={render.error ?? revisionQuery.error}
          fallbackDetail="הפנייה לשרת נכשלה. הגרסה המאושרת נשמרה."
          fallbackTitle="לא ניתן להתחיל את יצירת הקובץ"
        />
      )}

      <div className="flex flex-wrap gap-3">
        {revision?.ready_qualified === true ? (
          <Link className={buttonClasses("primary")} to={appRoutes.revision(revision.id)}>
            צפייה בגרסה המוכנה
          </Link>
        ) : (
          <Button
            disabled={revision === undefined}
            onClick={() => render.mutate()}
            pending={render.isPending}
            pendingLabel="מתחיל רינדור…"
          >
            יצירת HTML ו־PDF
          </Button>
        )}
      </div>
    </section>
  );
};
