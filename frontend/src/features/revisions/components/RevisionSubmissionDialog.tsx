import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { invalidateApplicationViews } from "@/api/applications";
import type { ApprovedRevision } from "@/api/contracts";
import { recordInternalSubmission } from "@/api/tracking";
import { ErrorCallout } from "@/app/ErrorCallout";
import { useAppForm } from "@/forms/useAppForm";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Checkbox } from "@/ui/Checkbox";
import { Dialog } from "@/ui/Dialog";
import { Field } from "@/ui/Field";
import { TextInput } from "@/ui/TextInput";
import { formatDateTime } from "@/ui/formatDateTime";
import { isoFromLocalDateTimeInput } from "@/ui/isoFromLocalDateTimeInput";
import { localDateTimeInputValue } from "@/ui/localDateTimeInputValue";

interface RevisionSubmissionDialogProps {
  onClose: () => void;
  onRecorded: () => void;
  open: boolean;
  /* When this revision is already on record as submitted. Its presence turns the dialog
     from the plain recording into the exception it now is, and the acknowledgement below
     is what the reader has to state before a second one can be written. */
  previousSubmittedAt: string | null;
  revision: ApprovedRevision;
}

export const RevisionSubmissionDialog = ({
  onClose,
  onRecorded,
  open,
  previousSubmittedAt,
  revision,
}: RevisionSubmissionDialogProps) => {
  const queryClient = useQueryClient();
  const [repeatAcknowledged, setRepeatAcknowledged] = useState(false);
  const form = useAppForm<{ submittedAt: string }>({
    defaultValues: { submittedAt: localDateTimeInputValue(new Date()) },
  });
  const submission = useMutation({
    mutationFn: ({ submittedAt }: { submittedAt: string }) => {
      const submittedAtIso = isoFromLocalDateTimeInput(submittedAt);
      if (revision.pdf_artifact_version_id == null || submittedAtIso === null) {
        throw new Error("Submission requires the exact Ready revision, PDF, and a valid date and time");
      }
      return recordInternalSubmission(revision.application_id, {
        approved_revision_id: revision.id,
        pdf_artifact_version_id: revision.pdf_artifact_version_id,
        submitted_at: submittedAtIso,
        metadata: {},
      });
    },
    onSuccess: () => {
      setRepeatAcknowledged(false);
      onClose();
      onRecorded();
      void invalidateApplicationViews(queryClient, revision.application_id);
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
            disabled={!submittedAtValid || (previousSubmittedAt !== null && !repeatAcknowledged)}
            form="revision-submission-form"
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
      title={previousSubmittedAt === null ? "רישום הגשה קבועה" : "רישום הגשה נוספת של אותה גרסה"}
    >
      <form id="revision-submission-form" onSubmit={form.handleSubmit((fields) => submission.mutate(fields))}>
        <p className="mb-4">
          הרישום קבוע ומתייחס לגרסה ולקובץ ה־PDF המוצגים במסך הזה. הוא לא יפתור גרסה אחרת או קובץ אחר בזמן השמירה.
        </p>
        {previousSubmittedAt === null ? null : (
          <div className="mb-4 flex flex-col gap-3">
            <Callout title="הגרסה הזו כבר נרשמה כמוגשת" tone="warning">
              {`ההגשה הקיימת נרשמה ${formatDateTime(previousSubmittedAt)}. הרישום הקיים לא ישתנה — יתווסף לו אירוע הגשה נוסף.`}
            </Callout>
            <Checkbox
              checked={repeatAcknowledged}
              hint="למשל הגשה חוזרת דרך ערוץ אחר. אם ההגשה כבר נרשמה, אין צורך לרשום אותה שוב."
              onChange={(event) => setRepeatAcknowledged(event.target.checked)}
            >
              אני מבקש לרשום הגשה נוספת של אותה גרסה
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
            <TextInput
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
