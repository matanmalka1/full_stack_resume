import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
  applicationDetailQueryOptions,
  invalidateApplicationViews,
  updateApplicationNotes,
} from "../../api/applications";
import type { ApplicationListItem } from "../../api/contracts";
import { setNextAction, transitionRecruitmentStatus } from "../../api/tracking";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";
import { ViewSwitch } from "../../ui/ViewSwitch";
import { cx } from "../../ui/cx";
import { useServerSyncedField } from "../useServerSyncedField";
import { RecruitmentHistoryPanel } from "./RecruitmentHistoryPanel";
import { RecruitmentSummary } from "./RecruitmentSummary";
import { type RecruitmentUpdateFields, RecruitmentUpdateForm } from "./RecruitmentUpdateForm";

const managerViews = [
  { label: "עדכון", value: "update" },
  { label: "היסטוריה", value: "history" },
] as const;

type ManagerView = (typeof managerViews)[number]["value"];

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

/* Every Application screen and the dashboard share this command surface. A status
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
  const [view, setView] = useState<ManagerView>("update");

  useEffect(() => {
    if (application === null) {
      initializedApplicationId.current = null;
      form.reset(emptyFields);
      setView("update");
    } else if (detail !== undefined && initializedApplicationId.current !== applicationId) {
      initializedApplicationId.current = applicationId;
      setView("update");
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

  const refresh = () => {
    if (application !== null) {
      void invalidateApplicationViews(queryClient, application.id);
    }
  };

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
      footer={
        detail === undefined ? undefined : (
          <>
            <Button disabled={save.isPending} onClick={onClose} variant="secondary">
              ביטול
            </Button>
            <Button
              disabled={!hasChanges}
              form="recruitment-update-form"
              pending={save.isPending}
              pendingLabel="שומר…"
              type="submit"
            >
              שמירת שינויים
            </Button>
          </>
        )
      }
      headingId="recruitment-update-heading"
      onClose={onClose}
      open={application !== null}
      size="wide"
      title={application === null ? "ניהול מועמדות" : `ניהול מועמדות: ${application.company}`}
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
            <div className="flex flex-col gap-5">
              <RecruitmentSummary detail={detail} />
              <div className="lg:hidden">
                <ViewSwitch label="בחירת אזור בניהול המועמדות" onChange={setView} options={managerViews} value={view} />
              </div>
              <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(19rem,0.9fr)]">
                <RecruitmentUpdateForm
                  detail={detail}
                  fields={fields}
                  form={form}
                  onSubmit={form.handleSubmit((values) => save.mutate(values))}
                  saveError={save.error}
                  serverChanged={
                    statusChangedOnServer || actionChangedOnServer || dateChangedOnServer || notesChangedOnServer
                  }
                  statusOptions={statusOptions}
                  visible={view === "update"}
                />
                <RecruitmentHistoryPanel
                  className={cx(view === "history" ? "block" : "hidden", "lg:block")}
                  detail={detail}
                  onChanged={refresh}
                />
              </div>
            </div>
          )}
        </>
      )}
    </Dialog>
  );
};
