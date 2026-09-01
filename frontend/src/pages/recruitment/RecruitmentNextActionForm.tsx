import { useMutation } from "@tanstack/react-query";

import type { ApplicationDetail } from "../../api/contracts";
import { setNextAction } from "../../api/tracking";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Field } from "../../ui/Field";
import { TextInput } from "../../ui/TextInput";
import { useServerSyncedField } from "../useServerSyncedField";

interface NextActionFields {
  action: string;
  date: string;
}

interface RecruitmentNextActionFormProps {
  detail: ApplicationDetail;
  onChanged: () => void;
}

export const RecruitmentNextActionForm = ({ detail, onChanged }: RecruitmentNextActionFormProps) => {
  const form = useAppForm<NextActionFields>({
    defaultValues: {
      action: detail.application.next_action ?? "",
      date: detail.application.next_action_date ?? "",
    },
  });
  const fields = form.watch();
  const actionChangedOnServer = useServerSyncedField({
    isDirty: form.formState.dirtyFields.action === true,
    localValue: fields.action,
    onSync: (value) => form.resetField("action", { defaultValue: value }),
    serverValue: detail.application.next_action ?? "",
  });
  const dateChangedOnServer = useServerSyncedField({
    isDirty: form.formState.dirtyFields.date === true,
    localValue: fields.date,
    onSync: (value) => form.resetField("date", { defaultValue: value }),
    serverValue: detail.application.next_action_date ?? "",
  });
  const mutation = useMutation({
    mutationFn: ({ clear, values }: { clear: boolean; values: NextActionFields }) =>
      setNextAction(detail.application.id, {
        next_action: clear ? null : values.action.trim() || null,
        next_action_date: clear ? null : values.date || null,
      }),
    /* Keep the submitted value dirty until the authoritative projection arrives. The
       server-sync hooks then accept that exact value as the new default; resetting here
       would briefly let the still-old projection overwrite a successful save. */
    onSuccess: onChanged,
  });
  const hasEnteredValue = fields.action.trim() !== "" || fields.date !== "";
  const hasSavedValue = detail.application.next_action != null || detail.application.next_action_date != null;

  return (
    <form
      className="flex flex-col gap-3 border-t border-cv-border pt-6 lg:border-s lg:border-t-0 lg:ps-6 lg:pt-0"
      onSubmit={form.handleSubmit((values) => mutation.mutate({ clear: false, values }))}
    >
      <div>
        <h3 className="font-semibold text-cv-text">הפעולה הבאה</h3>
        <p className="mt-1 text-support text-cv-text-muted">תזכורת אחת ממוקדת להמשך הטיפול.</p>
      </div>
      {mutation.error === null ? null : (
        <ErrorCallout
          error={mutation.error}
          fallbackDetail="הפעולה לא נשמרה. הרשומות הקיימות לא השתנו."
          fallbackTitle="לא ניתן לעדכן את הפעולה הבאה"
        />
      )}
      {actionChangedOnServer || dateChangedOnServer ? (
        <Callout role="status" title="הפעולה הבאה השתנתה בשרת" tone="warning">
          הערכים שהקלדת נשמרו בטופס ולא הוחלפו. כדאי לבדוק אותם לפני השמירה.
        </Callout>
      ) : null}
      <Field label="מה לעשות">{(control) => <TextInput {...control} {...form.register("action")} />}</Field>
      <Field label="תאריך">{(control) => <TextInput {...control} {...form.register("date")} type="date" />}</Field>
      <div className="flex flex-wrap justify-end gap-2 pt-1">
        <Button
          disabled={mutation.isPending || !hasSavedValue}
          onClick={() => mutation.mutate({ clear: true, values: form.getValues() })}
          variant="ghost"
        >
          הסרת התזכורת
        </Button>
        <Button disabled={!form.formState.isDirty || !hasEnteredValue} pending={mutation.isPending} type="submit">
          שמירת הפעולה
        </Button>
      </div>
    </form>
  );
};
