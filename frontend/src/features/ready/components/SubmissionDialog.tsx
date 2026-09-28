import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { invalidateDocumentViews } from "@/api/documents";

import { recordInternalSubmission } from "@/api/tracking";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { useAppForm } from "@/hooks/useAppForm";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Checkbox } from "@/ui/Checkbox";
import { Dialog } from "@/ui/Dialog";
import { Field } from "@/ui/Field";
import { Input } from "@/ui/Input";
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

export const SubmissionDialog = ({
  applicationId,
  documentHash,
  onClose,
  onRecorded,
  open,
  previousSubmittedAt,
}: SubmissionDialogProps) => {
  const queryClient = useQueryClient();
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
          <Button onClick={close} variant="secondary">
            חזרה
          </Button>
          <Button
            disabled={!submittedAtValid || (previousShown !== null && !repeatAcknowledged)}
            form="document-submission-form"
            pending={submission.isPending}
            pendingLabel="רושם…"
            type="submit"
          >
            אישור ורישום ההגשה
          </Button>
        </>
      }
      headingId="submission-dialog-heading"
      onClose={close}
      open={open}
      title={previousShown === null ? "רישום הגשה קבועה" : "רישום הגשה נוספת של אותם קורות חיים"}
    >
      <form id="document-submission-form" onSubmit={form.handleSubmit((fields) => submission.mutate(fields))}>
        <p className="mb-4">
          הרישום קבוע: הוא שומר עותק של התוכן ושל קובצי ה־HTML וה־PDF המוצגים במסך הזה. אם המסמך השתנה מאז שנפתח, הרישום
          יסורב ולא יירשם מסמך אחר.
        </p>
        {previousShown === null ? null : (
          <div className="mb-4 flex flex-col gap-3">
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
        {submission.error === null ? null : (
          <ErrorCallout
            error={submission.error}
            fallbackDetail="ההגשה לא נרשמה וההיסטוריה לא השתנתה."
            fallbackTitle="לא ניתן לרשום את ההגשה"
          />
        )}
        <Field error={form.formState.errors.submittedAt?.message} label="מועד ההגשה">
          {(control) => (
            <Input
              {...control}
              {...form.register("submittedAt", {
                required: "יש להזין מועד הגשה.",
                validate: (value) => isoFromLocalDateTimeInput(value) !== null || "יש להזין מועד הגשה תקין.",
              })}
              required
              type="datetime-local"
            />
          )}
        </Field>
      </form>
    </Dialog>
  );
};
