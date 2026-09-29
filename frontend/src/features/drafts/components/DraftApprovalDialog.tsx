import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiProblem } from "@/api/client";
import type { ApplicationDetail, DocumentCheck } from "@/api/contracts";
import { approveDocument, invalidateDocumentViews } from "@/api/documents";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Checkbox } from "@/ui/Checkbox";
import { Dialog } from "@/ui/Dialog";
import { SummaryList } from "@/ui/SummaryList";
import type { EditableDocument } from "../model/drafts.types";

interface DraftApprovalDialogProps {
  applicationId: string;
  detail: ApplicationDetail | undefined;
  draft: EditableDocument | undefined;
  /* The approval landed: the document is approved at the hash the result names. */
  onApproved: (result: DocumentCheck) => void;
  /* The check ran again under approval and failed. The report is data (§15), shown by the
     check panel once the document is read back. */
  onCheckFailed: () => void;
  onClose: () => void;
  /* Refused because the document changed: the editor shows the reason on its check panel
     rather than sending the user to a screen for it. */
  onStale: () => void;
  open: boolean;
}

/* A.4 frame 5's approval dialog, opened from the editor holding the document it approves.

   §15 `approve_document` is synchronous and runs the check itself, so the dialog is the
   one explicit confirmation - including of the non-blocking warnings the stored report
   carries - and the command either approves this exact document or returns why not. */
export const DraftApprovalDialog = ({
  applicationId,
  detail,
  draft,
  onApproved,
  onCheckFailed,
  onClose,
  onStale,
  open,
}: DraftApprovalDialogProps) => {
  const queryClient = useQueryClient();
  const [acknowledged, setAcknowledged] = useState(false);
  const warnings = draft?.content_report?.issues.filter((issue) => !issue.hard) ?? [];

  const approval = useMutation({
    mutationFn: async () => {
      if (draft === undefined) {
        throw new Error("Approval requires the exact document on screen");
      }
      return approveDocument(applicationId, draft.document_hash);
    },
    onSuccess: async (result) => {
      await invalidateDocumentViews(queryClient, applicationId);
      if (result.passed && result.preparation_state !== "draft_in_progress") onApproved(result);
      else onCheckFailed();
    },
    onError: (error) => {
      if (error instanceof ApiProblem && error.problem.code === "DOCUMENT_CHANGED") {
        void invalidateDocumentViews(queryClient, applicationId);
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
            disabled={warnings.length > 0 && !acknowledged}
            onClick={() => approval.mutate()}
            pending={approval.isPending}
            pendingLabel="מאשר ומכין…"
          >
            אישור והכנת PDF
          </Button>
        </>
      }
      headingId="approval-dialog-heading"
      onClose={onClose}
      open={open}
      title="אישור והכנת PDF"
    >
      <p>
        בדקתי את קורות החיים ואני מאשר/ת את הגרסה הזו להפקת PDF. עריכה אחרי האישור תחזיר את המסמך לטיוטה ותדרוש אישור
        חדש.
      </p>
      {/* What is being approved, set apart from the sentence that approves it: it ran
          straight on from the paragraph with no space between the two. */}
      {detail === undefined || draft === undefined ? null : (
        <div className="mt-section-gap rounded-control border border-cv-border bg-cv-surface p-card-padding">
          <SummaryList
            items={[
              { term: "חברה", value: detail.application.company },
              { term: "תפקיד", value: detail.application.target_role },
              { term: "מזהה המסמך", value: draft.document_hash.slice(0, 12), ltr: true, mono: true },
            ]}
          />
        </div>
      )}
      {approval.error === null ||
      (approval.error instanceof ApiProblem && approval.error.problem.code === "DOCUMENT_CHANGED") ? null : (
        <ErrorCallout
          className="mt-4"
          error={approval.error}
          fallbackDetail="המסמך לא השתנה. אפשר לנסות שוב."
          title="המסמך לא אושר"
        />
      )}
      {warnings.length === 0 ? null : (
        <Callout className="mt-4" title="נותרו אזהרות לא חוסמות" tone="warning">
          <ul className="mb-3 list-disc ps-5">
            {warnings.map((warning) => (
              <li dir="auto" key={`${warning.code}:${warning.message}`}>
                {warning.message}
              </li>
            ))}
          </ul>
          <Checkbox checked={acknowledged} onChange={(event) => setAcknowledged(event.currentTarget.checked)}>
            קראתי את האזהרות ואני רוצה להמשיך באישור
          </Checkbox>
        </Callout>
      )}
    </Dialog>
  );
};
