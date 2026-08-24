import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { applicationDetailQueryKey, applicationDetailQueryOptions } from "../api/applications";
import { ApiProblem } from "../api/client";
import { workingDraftQueryOptions } from "../api/drafts";
import { approveWorkingDraft, validationRunQueryOptions } from "../api/validation";
import { ActionBar } from "../ui/ActionBar";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { Checkbox } from "../ui/Checkbox";
import { Dialog } from "../ui/Dialog";
import { PageHeading } from "../ui/PageHeading";
import { SummaryList } from "../ui/SummaryList";
import { ValidationReportView } from "./ValidationReportView";

export const ApprovalPage = () => {
  const { applicationId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  if (applicationId === undefined) throw new Error("ApprovalPage requires applicationId");

  const application = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = application.data;
  const draftId = detail?.active_working_draft_id ?? null;
  const draftQuery = useQuery({ ...workingDraftQueryOptions(draftId ?? ""), enabled: draftId !== null });
  const draft = draftQuery.data?.draft;
  const runId = searchParams.get("validation_run_id") ?? draft?.latest_validation_run_id ?? null;
  const runQuery = useQuery({ ...validationRunQueryOptions(runId ?? ""), enabled: runId !== null });
  const run = runQuery.data;
  const warnings = run?.report.issues.filter((issue) => !issue.hard) ?? [];
  const approvalKey = useMemo(
    () => draft === undefined || runId === null ? "" : `${draft.id}:${draft.edit_version}:${runId}`,
    [draft, runId],
  );

  const approval = useMutation({
    mutationFn: async () => {
      if (draft === undefined || runId === null) throw new Error("Approval requires an exact draft and validation run");
      return approveWorkingDraft(draft.id, draft.edit_version, runId, approvalKey);
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
      void navigate(`/approved-revisions/${encodeURIComponent(result.revision_id)}/render`);
    },
    onError: (error) => {
      if (error instanceof ApiProblem && error.problem.code === "VALIDATION_STALE") {
        void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
        void navigate(`/applications/${encodeURIComponent(applicationId)}/validation?reason=stale`, { replace: true });
      }
    },
  });
  const exactPassingRun = run?.passed === true && draft !== undefined && run.edit_version === draft.edit_version;

  return (
    <Card aria-labelledby="route-heading">
      <PageHeading id="route-heading" description="האישור יוצר גרסה קבועה שאינה ניתנת לשינוי.">
        אישור הגרסה
      </PageHeading>
      <div className="mt-6 flex flex-col gap-6">
        {detail === undefined || draft === undefined || run === undefined ? (
          <p className="text-body text-cv-text-muted">טוען את פרטי האישור…</p>
        ) : (
          <>
            <SummaryList items={[
              { term: "חברה", value: detail.application.company },
              { term: "תפקיד", value: detail.application.target_role },
              { term: "גרסת טיוטה", value: draft.edit_version, ltr: true },
              { term: "ValidationRun", value: run.validation_run_id, ltr: true },
            ]} />
            <ValidationReportView report={run.report} />
          </>
        )}
        {approval.error === null || (approval.error instanceof ApiProblem && approval.error.problem.code === "VALIDATION_STALE") ? null : (
          <Callout role="alert" title="האישור לא בוצע" tone="blocker">
            {approval.error instanceof ApiProblem ? approval.error.problem.detail : "הפנייה לשרת נכשלה."}
          </Callout>
        )}
        {!exactPassingRun && run !== undefined ? (
          <Callout title="נדרש אימות עדכני שעבר" tone="blocker" />
        ) : null}
        <ActionBar
          primary={<Button disabled={!exactPassingRun} onClick={() => { setAcknowledged(false); setOpen(true); }}>פתיחת אישור</Button>}
          secondary={<Link className={buttonClasses("secondary")} to={`/applications/${encodeURIComponent(applicationId)}/validation`}>חזרה לאימות</Link>}
        />
      </div>
      <Dialog
        dismissible={false}
        footer={<><Button onClick={() => setOpen(false)} variant="secondary">חזרה</Button><Button disabled={approval.isPending || (warnings.length > 0 && !acknowledged)} onClick={() => approval.mutate()}>{approval.isPending ? "מאשר…" : "אישור הגרסה"}</Button></>}
        headingId="approval-dialog-heading"
        onClose={() => setOpen(false)}
        open={open}
        title="אישור גרסה קבועה"
      >
        <p>האישור יוצר רשומה קבועה מהטיוטה ומריצת האימות המוצגות כאן.</p>
        {warnings.length === 0 ? null : (
          <Checkbox checked={acknowledged} className="mt-4" onChange={(event) => setAcknowledged(event.currentTarget.checked)}>
            קראתי את האזהרות ואני רוצה להמשיך באישור
          </Checkbox>
        )}
      </Dialog>
    </Card>
  );
};
