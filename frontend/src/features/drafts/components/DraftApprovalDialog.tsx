import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, TriangleAlert } from "lucide-react";
import { useState } from "react";

import { ApiProblem } from "@/api/client";
import type { ApplicationDetail, DocumentCheck } from "@/api/contracts";
import { approveDocument, invalidateDocumentViews } from "@/api/documents";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button } from "@/ui/Button";
import { Checkbox } from "@/ui/Checkbox";
import { Dialog } from "@/ui/Dialog";
import { LtrText } from "@/ui/LtrText";
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

  /* What is being approved, as the design lists it: term at the start, value at the end,
     each pair a row of one recessed panel. */
  const facts =
    detail === undefined || draft === undefined
      ? []
      : [
          { term: "חברה", value: <span dir="auto">{detail.application.company}</span> },
          { term: "תפקיד", value: <span dir="auto">{detail.application.target_role}</span> },
          { term: "מזהה המסמך", value: <LtrText mono>{draft.document_hash.slice(0, 12)}</LtrText> },
        ];

  return (
    <Dialog
      dismissible={false}
      footer={
        <>
          <Button onClick={onClose} size="default" variant="secondary">
            ביטול
          </Button>
          <Button
            disabled={warnings.length > 0 && !acknowledged}
            onClick={() => approval.mutate()}
            pending={approval.isPending}
            pendingLabel="מאשר ומכין…"
            /* The design gives the command the wider share of a phone's row; tightened,
               its label holds one line in an equal half. */
            className="max-lg:px-3 max-lg:whitespace-nowrap"
            size="default"
          >
            <Check aria-hidden="true" className="size-icon-md" />
            אישור והכנת PDF
          </Button>
        </>
      }
      headingId="approval-dialog-heading"
      onClose={onClose}
      open={open}
      title="אישור והכנת PDF"
    >
      <div className="flex flex-col gap-4.5">
        {facts.length === 0 ? null : (
          <dl className="overflow-hidden rounded-control-lg border border-cv-hairline bg-cv-canvas">
            {facts.map((fact) => (
              <div
                className="flex items-baseline justify-between gap-3 border-t border-cv-hairline px-4 py-3 text-label first:border-t-0 max-lg:px-3.5"
                key={fact.term}
              >
                <dt className="text-cv-text-muted">{fact.term}</dt>
                <dd className="min-w-0 truncate font-bold">{fact.value}</dd>
              </div>
            ))}
          </dl>
        )}
        {approval.error === null ||
        (approval.error instanceof ApiProblem && approval.error.problem.code === "DOCUMENT_CHANGED") ? null : (
          <ErrorCallout error={approval.error} fallbackDetail="המסמך לא השתנה. אפשר לנסות שוב." title="המסמך לא אושר" />
        )}
        {/* The warnings the check left standing are the one thing to read before the
            command: the approval acknowledges them explicitly. */}
        {warnings.length === 0 ? null : (
          <section
            aria-labelledby="approval-warnings-heading"
            className="flex flex-col gap-2.5 rounded-control-lg bg-cv-surface-muted px-3.5 py-3 text-label"
          >
            <h3 className="flex items-center gap-2.5 font-bold" id="approval-warnings-heading">
              <TriangleAlert aria-hidden="true" className="size-icon-md shrink-0" />
              נותרו אזהרות לא חוסמות
            </h3>
            <ul className="list-disc ps-5 text-support leading-6">
              {warnings.map((warning) => (
                <li dir="auto" key={`${warning.code}:${warning.message}`}>
                  {warning.message}
                </li>
              ))}
            </ul>
            <Checkbox checked={acknowledged} onChange={(event) => setAcknowledged(event.currentTarget.checked)}>
              קראתי את האזהרות ואני רוצה להמשיך באישור
            </Checkbox>
          </section>
        )}
      </div>
    </Dialog>
  );
};
