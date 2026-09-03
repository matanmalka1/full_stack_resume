import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import type { ApplicationDetail, RecruitmentStatus } from "../../api/contracts";
import { correctRecruitmentStatus } from "../../api/tracking";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Dialog } from "../../ui/Dialog";
import { Field } from "../../ui/Field";
import { FormActions } from "../../ui/FormActions";
import { Select } from "../../ui/Select";
import { TextArea } from "../../ui/TextInput";
import { recruitmentStatusLabel, recruitmentStatusLabels } from "../application/applicationLabels";
import { useServerSyncedField } from "../useServerSyncedField";
import { statusEventLabel } from "./RecruitmentTimeline";

const allStatuses = Object.keys(recruitmentStatusLabels) as RecruitmentStatus[];

interface CorrectionFields {
  correctsEventId: string;
  reason: string;
  target: RecruitmentStatus;
}

interface RecruitmentCorrectionActionProps {
  detail: ApplicationDetail;
  onChanged: () => void;
}

export const RecruitmentCorrectionAction = ({ detail, onChanged }: RecruitmentCorrectionActionProps) => {
  const statusEvents = detail.recruitment_timeline.filter(
    (event) => event.item_type === "status_transition" || event.item_type === "status_correction",
  );
  const [open, setOpen] = useState(false);
  const form = useAppForm<CorrectionFields>({
    defaultValues: {
      correctsEventId: statusEvents.at(-1)?.id ?? "",
      reason: "",
      target: detail.recruitment_status as RecruitmentStatus,
    },
  });
  const fields = form.watch();
  const eventChangedOnServer = useServerSyncedField({
    isDirty: form.formState.dirtyFields.correctsEventId === true,
    localValue: fields.correctsEventId,
    onSync: (value) => form.resetField("correctsEventId", { defaultValue: value }),
    serverValue: statusEvents.at(-1)?.id ?? "",
  });
  const correction = useMutation({
    mutationFn: (values: CorrectionFields) =>
      correctRecruitmentStatus(detail.application.id, {
        target_status: values.target,
        corrects_event_id: values.correctsEventId,
        reason: values.reason,
      }),
    onSuccess: () => {
      form.resetField("reason", { defaultValue: "" });
      setOpen(false);
      onChanged();
    },
  });

  return (
    <>
      <Button onClick={() => setOpen(true)} variant="secondary">
        תיקון אירוע שנרשם
      </Button>

      <Dialog
        headingId="recruitment-correction-heading"
        onClose={() => setOpen(false)}
        open={open}
        title="תיקון אירוע שנרשם"
      >
        {statusEvents.length === 0 ? (
          <p className="text-support text-cv-text-muted">אין אירוע מצב שניתן לתקן.</p>
        ) : (
          <form
            className="grid gap-3 lg:grid-cols-2"
            id="recruitment-correction-form"
            onSubmit={form.handleSubmit((values) => correction.mutate(values))}
          >
            {correction.error === null ? null : (
              <ErrorCallout
                className="lg:col-span-2"
                error={correction.error}
                fallbackDetail="אירוע התיקון לא נוסף. הרשומות הקיימות לא השתנו."
                fallbackTitle="לא ניתן לתקן את האירוע"
              />
            )}
            {eventChangedOnServer ? (
              <Callout className="lg:col-span-2" role="status" title="ציר הזמן השתנה בשרת" tone="warning">
                האירוע שבחרת נשמר בטופס ולא הוחלף. כדאי לבדוק אותו לפני השמירה.
              </Callout>
            ) : null}
            <Field label="האירוע השגוי">
              {(control) => (
                <Select {...control} {...form.register("correctsEventId")}>
                  {statusEvents.map((item) => (
                    <option key={item.id} value={item.id}>
                      {statusEventLabel(item)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label="המצב הנכון">
              {(control) => (
                <Select {...control} {...form.register("target")}>
                  {allStatuses.map((status) => (
                    <option key={status} value={status}>
                      {recruitmentStatusLabel(status)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field className="lg:col-span-2" label="למה נדרש תיקון">
              {(control) => <TextArea {...control} {...form.register("reason")} required />}
            </Field>
            <FormActions className="lg:col-span-2">
              <Button onClick={() => setOpen(false)} variant="secondary">
                ביטול
              </Button>
              <Button disabled={fields.reason.trim() === ""} pending={correction.isPending} type="submit">
                הוספת אירוע תיקון
              </Button>
            </FormActions>
          </form>
        )}
      </Dialog>
    </>
  );
};
