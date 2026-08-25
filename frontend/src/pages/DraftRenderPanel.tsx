import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiProblem } from "../api/client";
import { operationQueryKey } from "../api/operations";
import { approvedRevisionQueryOptions, renderApprovedRevision } from "../api/revisions";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";

interface DraftRenderPanelProps {
  approvedRevisionId: string;
}

/* A.4 frame 6's render step, inline in the workspace that produced the revision.
   Rendering stays an explicit action with its own retry: it queues a durable Operation
   and it can fail on its own, and a render that fired itself on approval would queue
   work the user never asked for and leave a failure with nothing that asked for it.
   Approval is what became one click; rendering is one more, in place. */
export const DraftRenderPanel = ({ approvedRevisionId }: DraftRenderPanelProps) => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const revisionQuery = useQuery(approvedRevisionQueryOptions(approvedRevisionId));
  const revision = revisionQuery.data;
  const renderKey = useMemo(() => `render:${approvedRevisionId}`, [approvedRevisionId]);

  const render = useMutation({
    mutationFn: async () => {
      if (revision === undefined) throw new Error("Render was offered before the revision loaded");
      return renderApprovedRevision(revision.id, revision.application_id, renderKey);
    },
    onSuccess: ({ operation, operationPath }) => {
      queryClient.setQueryData(operationQueryKey(operation.id), operation);
      void navigate(operationPath);
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
          הגרסה שאושרה נשמרה כרשומה קבועה. יצירת הקובץ היא פעולה נפרדת, והגרסה נשארת מאושרת
          גם אם היא נכשלת.
        </p>
      </div>

      {revisionQuery.error === null && render.error === null ? null : (
        <Callout role="alert" title="לא ניתן להתחיל את יצירת הקובץ" tone="blocker">
          {(render.error ?? revisionQuery.error) instanceof ApiProblem
            ? ((render.error ?? revisionQuery.error) as ApiProblem).problem.detail
            : "הפנייה לשרת נכשלה. הגרסה המאושרת נשמרה."}
        </Callout>
      )}

      <div className="flex flex-wrap gap-3">
        {revision?.ready_qualified === true ? (
          <Link
            className={buttonClasses("primary")}
            to={`/approved-revisions/${encodeURIComponent(revision.id)}/ready`}
          >
            צפייה בגרסה המוכנה
          </Link>
        ) : (
          <Button
            disabled={revision === undefined || render.isPending}
            onClick={() => render.mutate()}
          >
            {render.isPending ? "מתחיל רינדור…" : "יצירת HTML ו־PDF"}
          </Button>
        )}
      </div>
    </section>
  );
};
