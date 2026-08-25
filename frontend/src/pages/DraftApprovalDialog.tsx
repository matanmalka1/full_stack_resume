import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { applicationDetailQueryKey } from "../api/applications";
import { ApiProblem } from "../api/client";
import type { ApplicationDetail, WorkingDraft } from "../api/contracts";
import { workingDraftQueryKey } from "../api/drafts";
import { approveWorkingDraft, validationRunQueryOptions } from "../api/validation";
import { Button } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Checkbox } from "../ui/Checkbox";
import { Dialog } from "../ui/Dialog";
import { LtrText } from "../ui/LtrText";
import { SummaryList } from "../ui/SummaryList";
import { TechnicalDetails } from "../ui/TechnicalDetails";

interface DraftApprovalDialogProps {
  applicationId: string;
  detail: ApplicationDetail | undefined;
  draft: WorkingDraft | undefined;
  onApproved: (revisionId: string) => void;
  onClose: () => void;
  /* Refused as stale: the workspace shows the reason on its validation panel rather
     than sending the user to a screen for it. */
  onStale: () => void;
  open: boolean;
  /* The exact passing run the validation panel confirmed. Approval is offered for no
     other run, so the dialog cannot name a version the evidence does not describe. */
  validationRunId: string | null;
}

/* A.4 frame 5's approval dialog. It was already specified as a dialog rather than a
   screen; this is that dialog, opened from the workspace holding the draft it approves.
   The command, the idempotency key, and the `VALIDATION_STALE` path are unchanged. */
export const DraftApprovalDialog = ({
  applicationId,
  detail,
  draft,
  onApproved,
  onClose,
  onStale,
  open,
  validationRunId,
}: DraftApprovalDialogProps) => {
  const queryClient = useQueryClient();
  const [acknowledged, setAcknowledged] = useState(false);

  const runQuery = useQuery({
    ...validationRunQueryOptions(validationRunId ?? ""),
    enabled: validationRunId !== null,
  });
  const run = runQuery.data;
  const warnings = run?.report.issues.filter((issue) => !issue.hard) ?? [];

  const approvalKey = useMemo(
    () =>
      draft === undefined || validationRunId === null
        ? ""
        : `${draft.id}:${draft.edit_version}:${validationRunId}`,
    [draft, validationRunId],
  );

  const approval = useMutation({
    mutationFn: async () => {
      if (draft === undefined || validationRunId === null) {
        throw new Error("Approval requires an exact draft and validation run");
      }
      return approveWorkingDraft(draft.id, draft.edit_version, validationRunId, approvalKey);
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
      onApproved(result.revision_id);
    },
    onError: (error) => {
      if (error instanceof ApiProblem && error.problem.code === "VALIDATION_STALE") {
        void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
        if (draft !== undefined) {
          void queryClient.invalidateQueries({ queryKey: workingDraftQueryKey(draft.id) });
        }
        onStale();
      }
    },
  });

  return (
    <Dialog
      dismissible={false}
      footer={
        <>
          <Button onClick={onClose} variant="secondary">
            חזרה
          </Button>
          <Button
            disabled={approval.isPending || (warnings.length > 0 && !acknowledged)}
            onClick={() => approval.mutate()}
          >
            {approval.isPending ? "מאשר…" : "אישור הגרסה"}
          </Button>
        </>
      }
      headingId="approval-dialog-heading"
      onClose={onClose}
      open={open}
      title="אישור גרסה קבועה"
    >
      <p>האישור יוצר רשומה קבועה מהטיוטה ומריצת האימות המדויקות הבאות.</p>
      {detail === undefined || draft === undefined || run === undefined ? null : (
        <div className="flex flex-col gap-3">
          <SummaryList
            items={[
              { term: "חברה", value: detail.application.company },
              { term: "תפקיד", value: detail.application.target_role },
              { term: "גרסת טיוטה", value: draft.edit_version, ltr: true },
              { term: "תוצאת אימות", value: run.passed ? "עברה" : "נכשלה" },
            ]}
          />
          <TechnicalDetails summary="פרטי ריצת האימות">
            <LtrText>{run.validation_run_id}</LtrText>
          </TechnicalDetails>
        </div>
      )}
      {approval.error === null ||
      (approval.error instanceof ApiProblem &&
        approval.error.problem.code === "VALIDATION_STALE") ? null : (
        <Callout className="mt-4" role="alert" title="האישור לא בוצע" tone="blocker">
          {approval.error instanceof ApiProblem
            ? approval.error.problem.detail
            : "הפנייה לשרת נכשלה."}
        </Callout>
      )}
      {warnings.length === 0 ? null : (
        <Callout className="mt-4" title="נותרו אזהרות לא חוסמות" tone="warning">
          <ul className="mb-3 list-disc ps-5">
            {warnings.map((warning, index) => (
              <li dir="auto" key={`${warning.code}-${index}`}>
                {warning.message}
              </li>
            ))}
          </ul>
          <Checkbox
            checked={acknowledged}
            onChange={(event) => setAcknowledged(event.currentTarget.checked)}
          >
            קראתי את האזהרות ואני רוצה להמשיך באישור
          </Checkbox>
        </Callout>
      )}
    </Dialog>
  );
};
