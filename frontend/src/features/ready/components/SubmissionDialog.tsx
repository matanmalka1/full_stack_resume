import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useState } from "react";

import { applicationDetailQueryOptions } from "@/api/applications";

import { invalidateDocumentViews } from "@/api/documents";

import { recordInternalSubmission } from "@/api/tracking";
import { PermanentRecordNote, SubmittedAtField, submittedAtRules } from "@/features/recruitment";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { useAppForm } from "@/hooks/useAppForm";
import { useServerFieldErrors } from "@/hooks/useServerFieldErrors";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Checkbox } from "@/ui/Checkbox";
import { Dialog } from "@/ui/Dialog";
import { formatDateTime } from "@/utils/formatDateTime";
import { isoFromLocalDateTimeInput } from "@/utils/isoFromLocalDateTimeInput";
import { localDateTimeInputValue } from "@/utils/localDateTimeInputValue";

interface SubmissionDialogProps {
  applicationId: string;
  /* The Ready document on screen. The submission names this exact hash (§18), so a document
     that changed after the reader looked at it is refused rather than recorded as sent. */
  documentHash: string;
  onClose: () => void;
  onRecorded: () => void;
  open: boolean;
  /* When this exact document is already on record as submitted. Its presence turns the
     dialog from the plain recording into the exception it now is, and the acknowledgement
     below is what the reader has to state before a second one can be written. */
  previousSubmittedAt: string | null;
}

const serverFields = { submitted_at: "submittedAt" } as const;

export const SubmissionDialog = ({
  applicationId,
  documentHash,
  onClose,
  onRecorded,
  open,
  previousSubmittedAt,
}: SubmissionDialogProps) => {
  const queryClient = useQueryClient();
  /* Which application is being sent, for the line under the title. The ready screen has
     already read this projection, so it is answered from the cache. */
  const application = useQuery(applicationDetailQueryOptions(applicationId)).data?.application;
  const [repeatAcknowledged, setRepeatAcknowledged] = useState(false);
  /* The native dialog keeps painting for its 0.18s exit transition after `open` turns
     false, and a successful recording invalidates the query that feeds
     `previousSubmittedAt`. Read live, the refetch lands mid-exit and the closing dialog
     briefly redraws as the repeat-submission variant. While closed, it keeps the value it
     last showed open. */
  const [shownWhileOpen, setShownWhileOpen] = useState(previousSubmittedAt);
  if (open && shownWhileOpen !== previousSubmittedAt) {
    setShownWhileOpen(previousSubmittedAt);
  }
  const previousShown = open ? previousSubmittedAt : shownWhileOpen;
  const form = useAppForm<{ submittedAt: string }>({
    defaultValues: { submittedAt: localDateTimeInputValue(new Date()) },
  });
  const submission = useMutation({
    mutationFn: ({ submittedAt }: { submittedAt: string }) => {
      const submittedAtIso = isoFromLocalDateTimeInput(submittedAt);
      if (submittedAtIso === null) {
        throw new Error("Submission requires a valid date and time");
      }
      return recordInternalSubmission(applicationId, {
        expected_document_hash: documentHash,
        submitted_at: submittedAtIso,
        metadata: {},
      });
    },
    onSuccess: () => {
      setRepeatAcknowledged(false);
      onClose();
      onRecorded();
      void invalidateDocumentViews(queryClient, applicationId);
    },
  });
  const inlineFields = useServerFieldErrors(submission.error, form.setError, serverFields);

  const close = () => {
    setRepeatAcknowledged(false);
    onClose();
  };
  const submittedAt = form.watch("submittedAt");
  const submittedAtValid = isoFromLocalDateTimeInput(submittedAt) !== null;

  return (
    <Dialog
      dismissible={false}
      footer={
        <>
          <Button onClick={close} size="default" variant="secondary">
            ביטול
          </Button>
          <Button
            disabled={!submittedAtValid || (previousShown !== null && !repeatAcknowledged)}
            form="document-submission-form"
            pending={submission.isPending}
            pendingLabel="רושם…"
            size="default"
            type="submit"
          >
            <Send aria-hidden="true" className="size-icon-md" />
            רישום הגשה
          </Button>
        </>
      }
      description={application === undefined ? undefined : `${application.company} · ${application.target_role}`}
      headingId="submission-dialog-heading"
      onClose={close}
      open={open}
      title={previousShown === null ? "רישום הגשה קבועה" : "רישום הגשה נוספת של אותם קורות חיים"}
    >
      <form
        className="flex flex-col gap-4"
        id="document-submission-form"
        onSubmit={form.handleSubmit((fields) => submission.mutate(fields))}
      >
        {previousShown === null ? null : (
          <div className="flex flex-col gap-3">
            <Callout title="קורות החיים האלה כבר נרשמו כמוגשים" tone="warning">
              {`ההגשה הקיימת נרשמה ${formatDateTime(previousShown)}. הרישום הקיים לא ישתנה — יתווסף לו אירוע הגשה נוסף.`}
            </Callout>
            <Checkbox
              checked={repeatAcknowledged}
              hint="למשל הגשה חוזרת דרך ערוץ אחר. אם ההגשה כבר נרשמה, אין צורך לרשום אותה שוב."
              onChange={(event) => setRepeatAcknowledged(event.target.checked)}
            >
              אני מבקש לרשום הגשה נוספת של אותם קורות חיים
            </Checkbox>
          </div>
        )}
        <SubmittedAtField
          error={form.formState.errors.submittedAt?.message}
          registration={form.register("submittedAt", submittedAtRules)}
        />
        {/* The document's content and its HTML and PDF are kept with the record; a document
            that changed since this screen opened is refused rather than recorded. */}
        <PermanentRecordNote>
          ההגשה תישמר יחד עם קורות החיים בדיוק כפי שנשלחו, גם אם המסמך ישתנה אחר כך.
        </PermanentRecordNote>
        {submission.error === null ? null : (
          <ErrorCallout
            error={submission.error}
            fallbackDetail="היסטוריית ההגשות לא השתנתה. אפשר לנסות שוב."
            inlineFields={inlineFields}
            title="ההגשה לא נרשמה"
          />
        )}
      </form>
    </Dialog>
  );
};
