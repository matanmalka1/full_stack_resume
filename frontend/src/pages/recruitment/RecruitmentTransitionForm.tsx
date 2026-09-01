import { useMutation } from "@tanstack/react-query";

import type { ApplicationDetail, TransitionableRecruitmentStatus } from "../../api/contracts";
import { transitionRecruitmentStatus } from "../../api/tracking";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Field } from "../../ui/Field";
import { Select } from "../../ui/Select";
import { TextInput } from "../../ui/TextInput";
import { recruitmentStatusLabel } from "../application/applicationLabels";
import { useServerSyncedField } from "../useServerSyncedField";

interface TransitionFields {
  reason: string;
  target: TransitionableRecruitmentStatus | "";
}

interface RecruitmentTransitionFormProps {
  detail: ApplicationDetail;
  onChanged: () => void;
}

export const RecruitmentTransitionForm = ({ detail, onChanged }: RecruitmentTransitionFormProps) => {
  const form = useAppForm<TransitionFields>({ defaultValues: { reason: "", target: "" } });
  const fields = form.watch();
  const changedOnServer = useServerSyncedField({
    changeToken: detail.allowed_recruitment_transitions.join("|"),
    /* Empty is the server-synced placeholder; every concrete choice is explicitly the
       user's. Deriving ownership from the value closes the render-sized gap in which RHF
       has published the new select value but has not published `dirtyFields` yet. */
    isDirty: fields.target !== "",
    localValue: fields.target,
    onSync: () => form.resetField("target", { defaultValue: "" }),
    serverValue: "",
  });
  const hasChoice = detail.allowed_recruitment_transitions.length > 0 || fields.target !== "";
  /* Keep the selected option's React identity when the server removes it from the allowed
     list. Rendering it through a separate conditional removes the selected DOM node first,
     which lets the browser reset an uncontrolled select to its placeholder mid-refresh. */
  const options =
    fields.target !== "" && !detail.allowed_recruitment_transitions.includes(fields.target)
      ? [fields.target, ...detail.allowed_recruitment_transitions]
      : detail.allowed_recruitment_transitions;
  const transition = useMutation({
    mutationFn: (values: TransitionFields) => {
      if (values.target === "") throw new Error("No transition target");
      return transitionRecruitmentStatus(detail.application.id, {
        target_status: values.target,
        reason: values.reason,
      });
    },
    onSuccess: () => {
      form.reset({ reason: "", target: "" });
      onChanged();
    },
  });

  return (
    <form className="flex flex-col gap-3" onSubmit={form.handleSubmit((values) => transition.mutate(values))}>
      <div>
        <h3 className="font-semibold text-cv-text">השלב בתהליך</h3>
        <p className="mt-1 text-support text-cv-text-muted">מעבר לשלב הבא הזמין בתהליך הגיוס.</p>
      </div>
      {transition.error === null ? null : (
        <ErrorCallout
          error={transition.error}
          fallbackDetail="השלב לא נשמר. הרשומות הקיימות לא השתנו."
          fallbackTitle="לא ניתן לעדכן את שלב הגיוס"
        />
      )}
      {changedOnServer ? (
        <Callout role="status" title="אפשרויות המעבר השתנו בשרת" tone="warning">
          הבחירה שלך נשמרה בטופס ולא הוחלפה. כדאי לבדוק אותה לפני השמירה.
        </Callout>
      ) : null}
      {!hasChoice ? (
        <p className="text-support text-cv-text-muted">אין מעבר ישיר זמין מהמצב הנוכחי.</p>
      ) : (
        <>
          <Field label="השלב הבא">
            {(control) => (
              <Select {...control} {...form.register("target")} value={fields.target}>
                <option key="placeholder" value="">
                  בחירת שלב
                </option>
                {options.map((status) => (
                  <option key={status} value={status}>
                    {recruitmentStatusLabel(status)}
                    {status === fields.target && !detail.allowed_recruitment_transitions.includes(status)
                      ? " · הבחירה שלך"
                      : ""}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="סיבה (רשות)">{(control) => <TextInput {...control} {...form.register("reason")} />}</Field>
          <div className="flex justify-end pt-1">
            <Button disabled={fields.target === ""} pending={transition.isPending} pendingLabel="שומר…" type="submit">
              שמירת השלב
            </Button>
          </div>
        </>
      )}
    </form>
  );
};
