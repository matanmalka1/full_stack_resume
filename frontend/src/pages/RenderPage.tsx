import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiProblem } from "../api/client";
import { operationQueryKey } from "../api/operations";
import { approvedRevisionQueryOptions, renderApprovedRevision } from "../api/revisions";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { PageHeading } from "../ui/PageHeading";
import { SummaryList } from "../ui/SummaryList";

export const RenderPage = () => {
  const { approvedRevisionId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  if (approvedRevisionId === undefined) throw new Error("RenderPage requires approvedRevisionId");
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
    <Card aria-labelledby="route-heading">
      <PageHeading id="route-heading" description="הרינדור הוא פעולה נפרדת. הגרסה נשארת מאושרת גם אם יצירת הקובץ נכשלת.">
        יצירת קובץ קורות החיים
      </PageHeading>
      <div className="mt-6 flex flex-col gap-6">
        {revision === undefined ? <p className="text-body text-cv-text-muted">טוען את הגרסה המאושרת…</p> : (
          <SummaryList items={[
            { term: "גרסה מאושרת", value: revision.id, ltr: true },
            { term: "מספר גרסה", value: revision.version_number, ltr: true },
            { term: "אושרה", value: revision.approved_at, ltr: true },
          ]} />
        )}
        {revisionQuery.error === null && render.error === null ? null : (
          <Callout role="alert" title="לא ניתן להתחיל את יצירת הקובץ" tone="blocker">
            {(render.error ?? revisionQuery.error) instanceof ApiProblem
              ? ((render.error ?? revisionQuery.error) as ApiProblem).problem.detail
              : "הפנייה לשרת נכשלה. הגרסה המאושרת נשמרה."}
          </Callout>
        )}
        <div className="flex flex-wrap gap-3">
          {revision?.ready_qualified === true ? (
            <Link className={buttonClasses("primary")} to={`/approved-revisions/${encodeURIComponent(revision.id)}/ready`}>צפייה בגרסה המוכנה</Link>
          ) : (
            <Button disabled={revision === undefined || render.isPending} onClick={() => render.mutate()}>
              {render.isPending ? "מתחיל רינדור…" : "יצירת HTML ו־PDF"}
            </Button>
          )}
          {revision === undefined ? null : (
            <Link className={buttonClasses("secondary")} to={`/applications/${encodeURIComponent(revision.application_id)}`}>חזרה למועמדות</Link>
          )}
        </div>
      </div>
    </Card>
  );
};
