import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import {
  applicationDetailQueryOptions,
  invalidateApplicationViews,
  updateApplicationNotes,
} from "../../api/applications";
import type { ApplicationListItem, TransitionableRecruitmentStatus } from "../../api/contracts";
import { setNextAction, transitionRecruitmentStatus } from "../../api/tracking";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Dialog } from "../../ui/Dialog";
import { Field } from "../../ui/Field";
import { FormActions } from "../../ui/FormActions";
import { Select } from "../../ui/Select";
import { TextArea, TextInput } from "../../ui/TextInput";
import { recruitmentStatusLabel } from "../application/applicationLabels";
import { useServerSyncedField } from "../useServerSyncedField";

interface RecruitmentUpdateFields {
  nextAction: string;
  nextActionDate: string;
  notes: string;
  reason: string;
  targetStatus: TransitionableRecruitmentStatus | "";
}

const emptyFields: RecruitmentUpdateFields = {
  nextAction: "",
  nextActionDate: "",
  notes: "",
  reason: "",
  targetStatus: "",
};

type RecruitmentUpdateTarget = Pick<ApplicationListItem, "company" | "id" | "target_role">;

interface RecruitmentUpdateDialogProps {
  application: RecruitmentUpdateTarget | null;
  onClose: () => void;
}

/* Dashboard and Application Detail intentionally share this command surface. A status
   transition, next action, and notes are one ordinary update from the user's point of
   view even though each value still goes to the application command that owns it. */
export const RecruitmentUpdateDialog = ({ application, onClose }: RecruitmentUpdateDialogProps) => {
  const queryClient = useQueryClient();
  const applicationId = application?.id ?? "";
  const detailQuery = useQuery({
    ...applicationDetailQueryOptions(applicationId),
    enabled: application !== null,
  });
  const detail = detailQuery.data;
  const form = useAppForm<RecruitmentUpdateFields>({ defaultValues: emptyFields });
  const fields = form.watch();
  const initializedApplicationId = useRef<string | null>(null);

  useEffect(() => {
    if (application === null) {
      initializedApplicationId.current = null;
      form.reset(emptyFields);
    } else if (detail !== undefined && initializedApplicationId.current !== applicationId) {
      initializedApplicationId.current = applicationId;
      form.reset({
        nextAction: detail.application.next_action ?? "",
        nextActionDate: detail.application.next_action_date ?? "",
        notes: detail.application.notes,
        reason: "",
        targetStatus: "",
      });
    }
  }, [application, applicationId, detail, form.reset]);

  const statusChangedOnServer = useServerSyncedField({
    changeToken: detail?.allowed_recruitment_transitions.join("|") ?? "",
    isDirty: fields.targetStatus !== "",
    localValue: fields.targetStatus,
    onSync: () => form.resetField("targetStatus", { defaultValue: "" }),
    serverValue: "",
  });
  const actionChangedOnServer = useServerSyncedField({
    isDirty: form.formState.dirtyFields.nextAction === true,
    localValue: fields.nextAction,
    onSync: (value) => form.resetField("nextAction", { defaultValue: value }),
    serverValue: detail?.application.next_action ?? "",
  });
  const dateChangedOnServer = useServerSyncedField({
    isDirty: form.formState.dirtyFields.nextActionDate === true,
    localValue: fields.nextActionDate,
    onSync: (value) => form.resetField("nextActionDate", { defaultValue: value }),
    serverValue: detail?.application.next_action_date ?? "",
  });
  const notesChangedOnServer = useServerSyncedField({
    isDirty: form.formState.dirtyFields.notes === true,
    localValue: fields.notes,
    onSync: (value) => form.resetField("notes", { defaultValue: value }),
    serverValue: detail?.application.notes ?? "",
  });
  const selectedStatus = fields.targetStatus;
  const statusOptions =
    detail !== undefined && selectedStatus !== "" && !detail.allowed_recruitment_transitions.includes(selectedStatus)
      ? [selectedStatus, ...detail.allowed_recruitment_transitions]
      : (detail?.allowed_recruitment_transitions ?? []);

  const save = useMutation({
    mutationFn: async (values: RecruitmentUpdateFields) => {
      if (detail === undefined) {
        throw new Error("Application detail is unavailable");
      }

      if (values.targetStatus !== "") {
        await transitionRecruitmentStatus(applicationId, {
          target_status: values.targetStatus,
          reason: values.reason,
        });
      }

      const nextAction = values.nextAction.trim() || null;
      const nextActionDate = values.nextActionDate || null;
      if (
        nextAction !== (detail.application.next_action ?? null) ||
        nextActionDate !== (detail.application.next_action_date ?? null)
      ) {
        await setNextAction(applicationId, {
          next_action: nextAction,
          next_action_date: nextActionDate,
        });
      }

      if (values.notes !== detail.application.notes) {
        await updateApplicationNotes(applicationId, {
          notes: values.notes,
          expected_notes: detail.application.notes,
        });
      }
    },
    onError: async () => {
      await invalidateApplicationViews(queryClient, applicationId);
    },
    onSuccess: async () => {
      await invalidateApplicationViews(queryClient, applicationId);
      onClose();
    },
  });

  const hasNextActionChange =
    detail !== undefined &&
    ((fields.nextAction.trim() || null) !== (detail.application.next_action ?? null) ||
      (fields.nextActionDate || null) !== (detail.application.next_action_date ?? null));
  const hasChanges =
    detail !== undefined &&
    (fields.targetStatus !== "" || hasNextActionChange || fields.notes !== detail.application.notes);

  return (
    <Dialog
      dismissible={!save.isPending}
      headingId="recruitment-update-heading"
      onClose={onClose}
      open={application !== null}
      title={application === null ? "עדכון מועמדות" : `עדכון סטטוס ומשימות: ${application.company}`}
    >
      {application === null ? null : (
        <>
          <p className="mb-4 truncate text-support text-cv-text-muted" dir="auto">
            {application.target_role}
          </p>
          {detailQuery.isPending ? (
            <p className="text-support text-cv-text-muted">טוען את פרטי המועמדות…</p>
          ) : detailQuery.error !== null ? (
            <ErrorCallout
              error={detailQuery.error}
              fallbackDetail="לא ניתן לפתוח את העדכון. אפשר לנסות שוב לאחר רענון המסך."
              fallbackTitle="טעינת פרטי המועמדות נכשלה"
            />
          ) : detail === undefined ? null : (
            <form className="flex flex-col gap-4" onSubmit={form.handleSubmit((values) => save.mutate(values))}>
              {save.error === null ? null : (
                <ErrorCallout
                  error={save.error}
                  fallbackDetail="ייתכן שחלק מהשינויים נשמרו. הערכים נטענו מחדש מהשרת; יש לבדוק אותם לפני ניסיון נוסף."
                  fallbackTitle="לא ניתן להשלים את העדכון"
                />
              )}
              {statusChangedOnServer || actionChangedOnServer || dateChangedOnServer || notesChangedOnServer ? (
                <Callout role="status" title="פרטי המועמדות השתנו בשרת" tone="warning">
                  הערכים שהקלדת נשמרו בטופס ולא הוחלפו. כדאי לבדוק אותם לפני השמירה.
                </Callout>
              ) : null}

              <Field label="מעבר לשלב הבא" optional>
                {(control) => (
                  <Select {...control} {...form.register("targetStatus")} value={fields.targetStatus}>
                    <option value="">ללא שינוי בשלב</option>
                    {statusOptions.map((status) => (
                      <option key={status} value={status}>
                        {recruitmentStatusLabel(status)}
                        {status === selectedStatus && !detail.allowed_recruitment_transitions.includes(status)
                          ? " · הבחירה שלך"
                          : ""}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>

              {fields.targetStatus === "" ? null : (
                <Field label="סיבת המעבר" optional>
                  {(control) => <TextInput {...control} {...form.register("reason")} />}
                </Field>
              )}

              <Field label="הצעד הבא" optional>
                {(control) => <TextInput {...control} {...form.register("nextAction")} dir="auto" />}
              </Field>
              <Field label="תאריך יעד" optional>
                {(control) => (
                  <TextInput {...control} {...form.register("nextActionDate")} className="ltr-island" type="date" />
                )}
              </Field>
              <Field label="הערות" optional>
                {(control) => <TextArea {...control} {...form.register("notes")} className="min-h-28" dir="auto" />}
              </Field>

              <FormActions divided>
                <Button disabled={save.isPending} onClick={onClose} variant="secondary">
                  ביטול
                </Button>
                <Button disabled={!hasChanges} pending={save.isPending} pendingLabel="שומר…" type="submit">
                  שמירת שינויים
                </Button>
              </FormActions>
            </form>
          )}
        </>
      )}
    </Dialog>
  );
};
