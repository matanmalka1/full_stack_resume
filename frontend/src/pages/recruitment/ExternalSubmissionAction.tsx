import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import type { ApplicationDetail } from "../../api/contracts";
import { recordExternalSubmission } from "../../api/tracking";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Dialog } from "../../ui/Dialog";
import { Field } from "../../ui/Field";
import { TextArea, TextInput } from "../../ui/TextInput";
import { isoFromLocalDateTimeInput } from "../../ui/isoFromLocalDateTimeInput";
import { localDateTimeInputValue } from "../../ui/localDateTimeInputValue";

interface ExternalSubmissionFields {
  note: string;
  submittedAt: string;
}

interface ExternalSubmissionActionProps {
  detail: ApplicationDetail;
  onChanged: () => void;
}

export const ExternalSubmissionAction = ({ detail, onChanged }: ExternalSubmissionActionProps) => {
  const [open, setOpen] = useState(false);
  const form = useAppForm<ExternalSubmissionFields>({
    defaultValues: { note: "", submittedAt: localDateTimeInputValue(new Date()) },
  });
  const submission = useMutation({
    mutationFn: (fields: ExternalSubmissionFields) => {
      const submittedAt = isoFromLocalDateTimeInput(fields.submittedAt);
      if (submittedAt === null) {
        throw new Error("invalid datetime-local value passed form validation");
      }
      return recordExternalSubmission(detail.application.id, {
        submitted_at: submittedAt,
        artifact_version_id: null,
        metadata: fields.note.trim() === "" ? {} : { note: fields.note.trim() },
      });
    },
    onSuccess: () => {
      form.resetField("note", { defaultValue: "" });
      setOpen(false);
      onChanged();
    },
  });

  return (
    <>
      <Button onClick={() => setOpen(true)} variant="secondary">
        רישום הגשה חיצונית
      </Button>

      <Dialog
        footer={
          <>
            <Button onClick={() => setOpen(false)} variant="secondary">
              ביטול
            </Button>
            <Button form="external-submission-form" pending={submission.isPending} pendingLabel="רושם…" type="submit">
              רישום ההגשה החיצונית
            </Button>
          </>
        }
        headingId="recruitment-external-heading"
        onClose={() => setOpen(false)}
        open={open}
        title="רישום הגשה שבוצעה מחוץ למערכת"
      >
        <form
          className="flex flex-col gap-3"
          id="external-submission-form"
          onSubmit={form.handleSubmit((fields) => submission.mutate(fields))}
        >
          {submission.error === null ? null : (
            <ErrorCallout
              error={submission.error}
              fallbackDetail="ההגשה לא נרשמה. הרשומות הקיימות לא השתנו."
              fallbackTitle="לא ניתן לרשום את ההגשה"
            />
          )}
          <Callout title="הרישום קבוע" tone="warning">
            ההגשה תתווסף להיסטוריה בלי להמציא גרסת קורות חיים או קובץ שלא נוצרו במערכת.
          </Callout>
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
          <Field label="הערה" optional>
            {(control) => <TextArea {...control} {...form.register("note")} />}
          </Field>
        </form>
      </Dialog>
    </>
  );
};
