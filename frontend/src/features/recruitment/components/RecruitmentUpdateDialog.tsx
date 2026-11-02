import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { applicationDetailQueryOptions, invalidateApplicationViews } from "@/api/applications";
import type { ApplicationDetail } from "@/api/contracts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { LiveRegion } from "@/ui/LiveRegion";
import { useRecruitmentUpdate } from "../hooks/useRecruitmentUpdate";
import type { RecruitmentManagerTarget } from "../model/recruitment.types";
import { RecruitmentHistoryPanel } from "./RecruitmentHistoryPanel";
import { RecruitmentUpdateForm } from "./RecruitmentUpdateForm";

interface RecruitmentDialogProps {
  application: RecruitmentManagerTarget | null;
  onClose: () => void;
}

interface DialogShape {
  description: ReactNode;
  headingId: string;
  size?: "default" | "wide";
  title: ReactNode;
}

/* The Application's projection, read for a dialog opened over a screen that may hold
   only a list item, with the wait and the failure drawn inside the dialog's own frame. */
const RecruitmentDialogLoader = ({
  application,
  children,
  onClose,
  shape,
}: RecruitmentDialogProps & { application: RecruitmentManagerTarget; shape: DialogShape } & {
  children: (detail: ApplicationDetail) => ReactNode;
}) => {
  const detailQuery = useQuery(applicationDetailQueryOptions(application.id));

  if (detailQuery.data !== undefined) return children(detailQuery.data);

  return (
    <Dialog {...shape} onClose={onClose} open>
      {detailQuery.error === null ? (
        <LiveRegion className="text-support text-cv-text-muted" visuallyHidden={false}>
          טוען את פרטי המועמדות…
        </LiveRegion>
      ) : (
        /* Not `QueryState`: its not-found answer replaces the whole route, which a
           dialog over the board must not do. */
        <ErrorCallout
          action={
            <Button onClick={() => void detailQuery.refetch()} variant="secondary">
              ניסיון חוזר
            </Button>
          }
          error={detailQuery.error}
          fallbackDetail="הבקשה לא הושלמה. אפשר לנסות שוב."
          label="שגיאה"
          title="לא ניתן לטעון את פרטי המועמדות"
        />
      )}
    </Dialog>
  );
};

const updateShape: DialogShape = {
  description: "עדכון ההתקדמות מול המעסיק.",
  headingId: "recruitment-update-heading",
  title: "עדכון סטטוס ומשימות",
};

const LoadedRecruitmentDialog = ({ detail, onClose }: { detail: ApplicationDetail; onClose: () => void }) => {
  const update = useRecruitmentUpdate(detail, onClose);

  return (
    <Dialog
      {...updateShape}
      dismissible={!update.save.isPending}
      footer={
        <>
          {/* A phone's sheet closes by its own mark and leaves the row to the command. */}
          <Button
            className="max-lg:hidden"
            disabled={update.save.isPending}
            onClick={onClose}
            size="default"
            variant="secondary"
          >
            ביטול
          </Button>
          <Button
            disabled={!update.hasChanges}
            form="recruitment-update-form"
            pending={update.save.isPending}
            pendingLabel="שומר…"
            size="default"
            type="submit"
          >
            עדכון
          </Button>
        </>
      }
      onClose={onClose}
      open
    >
      <RecruitmentUpdateForm
        detail={detail}
        fields={update.fields}
        form={update.form}
        inlineFields={update.inlineFields}
        onSubmit={update.form.handleSubmit((values) => update.save.mutate(values))}
        saveError={update.save.error}
        serverChanged={update.serverChanged}
        statusOptions={update.statusOptions}
      />
    </Dialog>
  );
};

/* The status sheet: where the application stands with the employer, the next thing to do
   and the reader's notes, in one form with one command. The board and the hub open the
   same sheet. What happened before - the events, corrections to them and submissions made
   outside the system - is the history dialog's, a separate command in the record's menu. */
export const RecruitmentUpdateDialog = ({ application, onClose }: RecruitmentDialogProps) =>
  application === null ? null : (
    <RecruitmentDialogLoader application={application} key={application.id} onClose={onClose} shape={updateShape}>
      {(detail) => <LoadedRecruitmentDialog detail={detail} onClose={onClose} />}
    </RecruitmentDialogLoader>
  );

/* The application's recruitment history: every status event, reminder and submission on
   record, with the two ways to add to it - a submission made outside the system, and a
   correction of an event recorded wrongly. History is only ever appended to. */
export const RecruitmentHistoryDialog = ({ application, onClose }: RecruitmentDialogProps) => {
  const queryClient = useQueryClient();
  if (application === null) return null;

  const shape: DialogShape = {
    description: <span dir="auto">{`${application.company} · ${application.target_role}`}</span>,
    headingId: "recruitment-history-dialog-heading",
    size: "wide",
    title: "היסטוריית המועמדות",
  };

  return (
    <RecruitmentDialogLoader application={application} key={application.id} onClose={onClose} shape={shape}>
      {(detail) => (
        <Dialog {...shape} onClose={onClose} open>
          <RecruitmentHistoryPanel
            detail={detail}
            onChanged={() => void invalidateApplicationViews(queryClient, application.id)}
          />
        </Dialog>
      )}
    </RecruitmentDialogLoader>
  );
};
