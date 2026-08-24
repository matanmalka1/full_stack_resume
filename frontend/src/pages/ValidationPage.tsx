import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { applicationDetailQueryKey, applicationDetailQueryOptions } from "../api/applications";
import { ApiProblem } from "../api/client";
import { workingDraftQueryOptions } from "../api/drafts";
import {
  validateWorkingDraft,
  validationRunQueryKey,
  validationRunQueryOptions,
} from "../api/validation";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { ActionBar } from "../ui/ActionBar";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { LiveRegion } from "../ui/LiveRegion";
import { PageHeading } from "../ui/PageHeading";
import { ValidationReportView } from "./ValidationReportView";

export const ValidationPage = () => {
  const { applicationId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const summaryRef = useRef<HTMLHeadingElement>(null);
  if (applicationId === undefined) throw new Error("ValidationPage requires applicationId");

  const application = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = application.data;
  useWorkflowStage(detail === undefined ? "unknown" : detail.preparation_state);
  const draftId = detail?.active_working_draft_id ?? null;
  const draftQuery = useQuery({ ...workingDraftQueryOptions(draftId ?? ""), enabled: draftId !== null });
  const draft = draftQuery.data?.draft;
  const requestedRunId = searchParams.get("validation_run_id");
  const runId = requestedRunId ?? draft?.latest_validation_run_id ?? null;
  const runQuery = useQuery({ ...validationRunQueryOptions(runId ?? ""), enabled: runId !== null });

  const validation = useMutation({
    mutationFn: async () => {
      if (draft === undefined) throw new Error("Validation was offered before the draft loaded");
      return validateWorkingDraft(draft.id, draft.edit_version);
    },
    onSuccess: (run) => {
      queryClient.setQueryData(validationRunQueryKey(run.validation_run_id), run);
      void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
      void navigate(
        `/applications/${encodeURIComponent(applicationId)}/validation?validation_run_id=${encodeURIComponent(run.validation_run_id)}`,
        { replace: true },
      );
    },
  });
  const run = validation.data ?? runQuery.data;
  useEffect(() => {
    if (validation.data !== undefined) summaryRef.current?.focus();
  }, [validation.data]);
  const staleNotice = searchParams.get("reason") === "stale";
  const error = application.error ?? draftQuery.error ?? runQuery.error ?? validation.error;

  return (
    <Card aria-labelledby="route-heading">
      <PageHeading id="route-heading" description="האימות בודק את גרסת הטיוטה המדויקת לפני אישור.">
        תוצאות האימות
      </PageHeading>
      <div className="mt-6 flex flex-col gap-6">
        {staleNotice ? (
          <Callout title="הטיוטה השתנתה מאז האימות" tone="warning">
            יש להריץ אימות חדש לגרסה הנוכחית. לא הופעל אישור ולא בוצע אימות מחדש אוטומטי.
          </Callout>
        ) : null}
        {error === null ? null : (
          <Callout role="alert" title="לא ניתן להשלים את האימות" tone="blocker">
            {error instanceof ApiProblem ? error.problem.detail : "הפנייה לשרת נכשלה."}
          </Callout>
        )}
        {draftId === null && detail !== undefined ? (
          <Callout title="אין טיוטה פעילה" tone="neutral" />
        ) : null}
        {run === undefined ? null : (
          <section aria-labelledby="validation-summary">
            <h2 className="mb-4 text-heading-sm font-semibold" id="validation-summary" ref={summaryRef} tabIndex={-1}>
              {run.passed ? "הטיוטה עברה אימות" : "האימות מצא חסימות"}
            </h2>
            <ValidationReportView report={run.report} />
          </section>
        )}
        <LiveRegion>
          {validation.data === undefined ? "" : validation.data.passed ? "האימות הושלם בהצלחה." : "האימות הושלם ונמצאו חסימות."}
        </LiveRegion>
        <ActionBar
          primary={
            run?.passed === true && draft !== undefined && run.edit_version === draft.edit_version ? (
              <Link
                className={buttonClasses("primary")}
                to={`/applications/${encodeURIComponent(applicationId)}/approval?validation_run_id=${encodeURIComponent(run.validation_run_id)}`}
              >
                מעבר לאישור
              </Link>
            ) : (
              <Button disabled={draft === undefined || validation.isPending} onClick={() => validation.mutate()}>
                {validation.isPending ? "מאמת…" : run === undefined ? "אימות הטיוטה" : "אימות מחדש"}
              </Button>
            )
          }
          secondary={
            <Link className={buttonClasses("secondary")} to={`/applications/${encodeURIComponent(applicationId)}/draft`}>
              חזרה לעריכה
            </Link>
          }
        />
      </div>
    </Card>
  );
};
