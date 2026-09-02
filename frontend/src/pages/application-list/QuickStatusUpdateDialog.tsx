import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { applicationDetailQueryOptions, invalidateApplicationViews, updateApplicationNotes } from "../../api/applications";
import type { ApplicationListItem, TransitionableRecruitmentStatus } from "../../api/contracts";
import { setNextAction, transitionRecruitmentStatus } from "../../api/tracking";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";
import { Field } from "../../ui/Field";
import { FormActions } from "../../ui/FormActions";
import { Select } from "../../ui/Select";
import { TextArea, TextInput } from "../../ui/TextInput";
import { recruitmentStatusLabel } from "../application/applicationLabels";

interface QuickStatusFields {
  nextAction: string;
  nextActionDate: string;
  notes: string;
  reason: string;
  targetStatus: TransitionableRecruitmentStatus | "";
}

const emptyFields: QuickStatusFields = {
  nextAction: "",
  nextActionDate: "",
  notes: "",
  reason: "",
  targetStatus: "",
};

interface QuickStatusUpdateDialogProps {
  application: ApplicationListItem | null;
  onClose: () => void;
}

export const QuickStatusUpdateDialog = ({ application, onClose }: QuickStatusUpdateDialogProps) => {
  const queryClient = useQueryClient();
  const applicationId = application?.id ?? "";
  const detailQuery = useQuery({
    ...applicationDetailQueryOptions(applicationId),
    enabled: application !== null,
  });
  const detail = detailQuery.data;
  const form = useAppForm<QuickStatusFields>({ defaultValues: emptyFields });
  const fields = form.watch();

  useEffect(() => {
    if (detail !== undefined) {
      form.reset({
        nextAction: detail.application.next_action ?? "",
        nextActionDate: detail.application.next_action_date ?? "",
        notes: detail.application.notes,
        reason: "",
        targetStatus: "",
      });
    }
  }, [detail, form.reset]);

  const save = useMutation({
    mutationFn: async (values: QuickStatusFields) => {
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
      headingId="quick-status-heading"
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
              fallbackDetail="לא ניתן לפתוח את העדכון המהיר. אפשר לנסות שוב או לעבור למסך המועמדות."
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

              <Field label="מעבר לשלב הבא" optional>
                {(control) => (
                  <Select {...control} {...form.register("targetStatus")} value={fields.targetStatus}>
                    <option value="">ללא שינוי בשלב</option>
                    {detail.allowed_recruitment_transitions.map((status) => (
                      <option key={status} value={status}>
                        {recruitmentStatusLabel(status)}
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
