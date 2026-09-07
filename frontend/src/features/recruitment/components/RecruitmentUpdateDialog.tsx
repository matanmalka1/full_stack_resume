import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import { applicationDetailQueryOptions, invalidateApplicationViews } from "@/api/applications";
import type { ApplicationDetail } from "@/api/contracts";
import { ErrorCallout } from "@/app/ErrorCallout";
import { Button } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { ViewSwitch } from "@/ui/ViewSwitch";
import { cx } from "@/ui/cx";
import { useRecruitmentUpdate } from "../hooks/useRecruitmentUpdate";
import type { RecruitmentManagerTarget } from "../recruitment.types";
import { RecruitmentHistoryPanel } from "./RecruitmentHistoryPanel";
import { RecruitmentSummary } from "./RecruitmentSummary";
import { RecruitmentUpdateForm } from "./RecruitmentUpdateForm";

const managerViews = [
  { label: "עדכון", value: "update" },
  { label: "היסטוריה", value: "history" },
] as const;

type ManagerView = (typeof managerViews)[number]["value"];

interface RecruitmentUpdateDialogProps {
  application: RecruitmentManagerTarget | null;
  onClose: () => void;
}

const DialogFrame = ({
  application,
  children,
  dismissible = true,
  footer,
  onClose,
}: {
  application: RecruitmentManagerTarget;
  children: ReactNode;
  dismissible?: boolean;
  footer?: ReactNode;
  onClose: () => void;
}) => (
  <Dialog
    dismissible={dismissible}
    footer={footer}
    headingId="recruitment-update-heading"
    onClose={onClose}
    open
    size="wide"
    title={`ניהול מועמדות: ${application.company}`}
  >
    <p className="mb-4 truncate text-support text-cv-text-muted" dir="auto">
      {application.target_role}
    </p>
    {children}
  </Dialog>
);

const LoadedRecruitmentDialog = ({
  application,
  detail,
  onClose,
}: {
  application: RecruitmentManagerTarget;
  detail: ApplicationDetail;
  onClose: () => void;
}) => {
  const queryClient = useQueryClient();
  const [view, setView] = useState<ManagerView>("update");
  const update = useRecruitmentUpdate(detail, onClose);
  const refresh = () => void invalidateApplicationViews(queryClient, application.id);

  return (
    <DialogFrame
      application={application}
      dismissible={!update.save.isPending}
      footer={
        <>
          <Button disabled={update.save.isPending} onClick={onClose} variant="secondary">
            ביטול
          </Button>
          <Button
            disabled={!update.hasChanges}
            form="recruitment-update-form"
            pending={update.save.isPending}
            pendingLabel="שומר…"
            type="submit"
          >
            שמירת שינויים
          </Button>
        </>
      }
      onClose={onClose}
    >
      <div className="flex flex-col gap-5">
        <RecruitmentSummary detail={detail} />
        <div className="lg:hidden">
          <ViewSwitch label="בחירת אזור בניהול המועמדות" onChange={setView} options={managerViews} value={view} />
        </div>
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(19rem,0.9fr)]">
          <RecruitmentUpdateForm
            detail={detail}
            fields={update.fields}
            form={update.form}
            onSubmit={update.form.handleSubmit((values) => update.save.mutate(values))}
            saveError={update.save.error}
            serverChanged={update.serverChanged}
            statusOptions={update.statusOptions}
            visible={view === "update"}
          />
          <RecruitmentHistoryPanel
            className={cx(view === "history" ? "block" : "hidden", "lg:block")}
            detail={detail}
            onChanged={refresh}
          />
        </div>
      </div>
    </DialogFrame>
  );
};

export const RecruitmentUpdateDialog = ({ application, onClose }: RecruitmentUpdateDialogProps) => {
  const applicationId = application?.id ?? "";
  const detailQuery = useQuery({
    ...applicationDetailQueryOptions(applicationId),
    enabled: application !== null,
  });

  if (application === null) return null;

  if (detailQuery.isPending) {
    return (
      <DialogFrame application={application} onClose={onClose}>
        <p className="text-support text-cv-text-muted">טוען את פרטי המועמדות…</p>
      </DialogFrame>
    );
  }

  if (detailQuery.error !== null) {
    return (
      <DialogFrame application={application} onClose={onClose}>
        <ErrorCallout
          error={detailQuery.error}
          fallbackDetail="לא ניתן לפתוח את העדכון. אפשר לנסות שוב לאחר רענון המסך."
          fallbackTitle="טעינת פרטי המועמדות נכשלה"
        />
      </DialogFrame>
    );
  }

  return detailQuery.data === undefined ? null : (
    <LoadedRecruitmentDialog
      application={application}
      detail={detailQuery.data}
      key={application.id}
      onClose={onClose}
    />
  );
};
