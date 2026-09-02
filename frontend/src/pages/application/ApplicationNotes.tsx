import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { invalidateApplicationViews, updateApplicationNotes } from "../../api/applications";
import type { ApplicationDetail } from "../../api/contracts";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Dialog } from "../../ui/Dialog";
import { Field } from "../../ui/Field";
import { FormActions } from "../../ui/FormActions";
import { TextArea } from "../../ui/TextInput";
import { useServerSyncedField } from "../useServerSyncedField";

interface NotesFields {
  notes: string;
}

export const ApplicationNotes = ({ detail }: { detail: ApplicationDetail }) => {
  const applicationId = detail.application.id;
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const form = useAppForm<NotesFields>({ defaultValues: { notes: detail.application.notes } });
  const notes = form.watch("notes");
  const changedOnServer = useServerSyncedField({
    isDirty: form.formState.dirtyFields.notes === true,
    localValue: notes,
    onSync: (value) => form.resetField("notes", { defaultValue: value }),
    serverValue: detail.application.notes,
  });
  const update = useMutation({
    mutationFn: (values: NotesFields) =>
      updateApplicationNotes(applicationId, {
        notes: values.notes,
        expected_notes: detail.application.notes,
      }),
    onSuccess: async () => {
      await invalidateApplicationViews(queryClient, applicationId);
      setOpen(false);
    },
  });

  return (
    <div className="mt-4 border-t border-cv-border pt-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-support font-semibold text-cv-text">הערות</h3>
          {detail.application.notes.trim() === "" ? (
            <p className="mt-2 text-support text-cv-text-muted">לא נוספו הערות למועמדות.</p>
          ) : (
            <p className="mt-2 whitespace-pre-wrap text-support leading-6 text-cv-text-muted" dir="auto">
              {detail.application.notes}
            </p>
          )}
        </div>
        <Button
          onClick={() => {
            update.reset();
            setOpen(true);
          }}
          variant="secondary"
        >
          עריכת הערות
        </Button>
      </div>

      <Dialog
        headingId="application-notes-heading"
        onClose={() => setOpen(false)}
        open={open}
        title="עריכת הערות למועמדות"
      >
        <form className="flex flex-col gap-4" onSubmit={form.handleSubmit((values) => update.mutate(values))}>
          {update.error === null ? null : (
            <ErrorCallout
              error={update.error}
              fallbackDetail="ההערות לא השתנו. הטקסט שהקלדת נשמר בטופס ואפשר לנסות שוב."
              fallbackTitle="לא ניתן לשמור את ההערות"
            />
          )}
          {changedOnServer ? (
            <Callout role="status" title="ההערות השתנו בשרת" tone="warning">
              הטקסט שהקלדת נשמר בטופס ולא הוחלף. כדאי לבדוק אותו לפני השמירה.
            </Callout>
          ) : null}
          <Field label="הערות">
            {(control) => <TextArea {...control} {...form.register("notes")} className="min-h-36" dir="auto" />}
          </Field>
          <FormActions>
            <Button onClick={() => setOpen(false)} variant="secondary">
              ביטול
            </Button>
            <Button disabled={!form.formState.isDirty} pending={update.isPending} pendingLabel="שומר…" type="submit">
              שמירת ההערות
            </Button>
          </FormActions>
        </form>
      </Dialog>
    </div>
  );
};
