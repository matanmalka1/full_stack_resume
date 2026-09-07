import { useMutation, useQueryClient } from "@tanstack/react-query";

import { invalidateApplicationViews, updateApplicationNotes } from "@/api/applications";
import type { ApplicationDetail } from "@/api/contracts";
import { setNextAction, transitionRecruitmentStatus } from "@/api/tracking";
import { useAppForm } from "@/forms/useAppForm";
import type { RecruitmentUpdateFields } from "../recruitment.types";
import { useServerSyncedField } from "./useServerSyncedField";

const initialFields = (detail: ApplicationDetail): RecruitmentUpdateFields => ({
  nextAction: detail.application.next_action ?? "",
  nextActionDate: detail.application.next_action_date ?? "",
  notes: detail.application.notes,
  reason: "",
  targetStatus: "",
});

export const useRecruitmentUpdate = (detail: ApplicationDetail, onSaved: () => void) => {
  const queryClient = useQueryClient();
  const applicationId = detail.application.id;
  const form = useAppForm<RecruitmentUpdateFields>({ defaultValues: initialFields(detail) });
  const fields = form.watch();

  const statusChangedOnServer = useServerSyncedField({
    changeToken: detail.allowed_recruitment_transitions.join("|"),
    isDirty: fields.targetStatus !== "",
    localValue: fields.targetStatus,
    onSync: () => form.resetField("targetStatus", { defaultValue: "" }),
    serverValue: "",
  });
  const actionChangedOnServer = useServerSyncedField({
    isDirty: form.formState.dirtyFields.nextAction === true,
    localValue: fields.nextAction,
    onSync: (value) => form.resetField("nextAction", { defaultValue: value }),
    serverValue: detail.application.next_action ?? "",
  });
  const dateChangedOnServer = useServerSyncedField({
    isDirty: form.formState.dirtyFields.nextActionDate === true,
    localValue: fields.nextActionDate,
    onSync: (value) => form.resetField("nextActionDate", { defaultValue: value }),
    serverValue: detail.application.next_action_date ?? "",
  });
  const notesChangedOnServer = useServerSyncedField({
    isDirty: form.formState.dirtyFields.notes === true,
    localValue: fields.notes,
    onSync: (value) => form.resetField("notes", { defaultValue: value }),
    serverValue: detail.application.notes,
  });

  const save = useMutation({
    mutationFn: async (values: RecruitmentUpdateFields) => {
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
    onError: () => invalidateApplicationViews(queryClient, applicationId),
    onSuccess: async () => {
      await invalidateApplicationViews(queryClient, applicationId);
      onSaved();
    },
  });

  const selectedStatus = fields.targetStatus;
  const statusOptions =
    selectedStatus !== "" && !detail.allowed_recruitment_transitions.includes(selectedStatus)
      ? [selectedStatus, ...detail.allowed_recruitment_transitions]
      : detail.allowed_recruitment_transitions;
  const hasNextActionChange =
    (fields.nextAction.trim() || null) !== (detail.application.next_action ?? null) ||
    (fields.nextActionDate || null) !== (detail.application.next_action_date ?? null);
  const hasChanges = fields.targetStatus !== "" || hasNextActionChange || fields.notes !== detail.application.notes;

  return {
    fields,
    form,
    hasChanges,
    save,
    serverChanged: statusChangedOnServer || actionChangedOnServer || dateChangedOnServer || notesChangedOnServer,
    statusOptions,
  };
};
