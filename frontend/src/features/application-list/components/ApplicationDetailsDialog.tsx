import { useQuery } from "@tanstack/react-query";
import { Download, ExternalLink, FileCheck2 } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { approvedRevisionQueryOptions, recruiterPdfHref } from "@/api/revisions";
import { routePaths } from "@/app/routePaths";
import { sourceHostname } from "@/features/applications";
import { preparationResumeDestination, preparationStateLabels, trackLabel } from "@/features/preparation";
import { Button, buttonClasses } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { formatDateTime } from "@/utils/formatDateTime";
import { preparationProgress } from "../model/applicationListPresentation";
import { ApplicationFitStatus, ApplicationRecruitmentStatus } from "./ApplicationListStatuses";
import { ApplicationRowNextAction } from "./ApplicationRowNextAction";

interface ApplicationDetailsDialogProps {
  application: ApplicationListItem | null;
  clearing: boolean;
  onClearNextAction: (item: ApplicationListItem) => void;
  onClose: () => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

const Fact = ({ children, label }: { children: ReactNode; label: string }) => (
  <div className="flex min-w-0 flex-col items-start gap-1">
    <span className="text-support text-cv-text-muted">{label}</span>
    <span className="text-support font-semibold text-cv-text">{children}</span>
  </div>
);

/* The finished CV, with its PDF one press away as demo_re offers it. The board row
   names only the revision, so the PDF's artifact comes from the revision itself - the
   same read, and the same recruiter-pdf delivery, the revision screen uses. A revision
   that did not qualify, or whose read has not arrived, offers no download: the
   revision screen stays one press away either way. */
const ReadyCv = ({ onClose, revisionId }: { onClose: () => void; revisionId: string }) => {
  const revision = useQuery(approvedRevisionQueryOptions(revisionId)).data;
  const pdfArtifactId = revision?.ready_qualified === true ? (revision.pdf_artifact_version_id ?? null) : null;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-cv-border p-3.5">
      <span className="inline-flex items-center gap-2 text-support text-cv-text">
        <FileCheck2 aria-hidden="true" className="size-icon-md shrink-0 text-cv-text-muted" />
        קורות חיים מוכנים למשרה זו
      </span>
      <span className="flex flex-wrap items-center gap-2">
        <Link
          className={buttonClasses("secondary", undefined, "compact")}
          onClick={onClose}
          to={routePaths.revision(revisionId)}
        >
          פתיחת הגרסה המוכנה
        </Link>
        {pdfArtifactId === null ? null : (
          <a
            className={buttonClasses("primary", undefined, "compact")}
            href={recruiterPdfHref(revisionId, pdfArtifactId)}
          >
            <Download aria-hidden="true" className="size-icon-sm" />
            הורדת PDF
          </a>
        )}
      </span>
    </div>
  );
};

/* One Application at a glance, laid out after demo_re's job-details modal: its four
   states side by side, what to do next, the finished CV, the posting, the reader's
   notes and when it was opened and last changed.

   It is read from the board's own row - only a finished CV's revision is fetched, for
   its PDF - and every block is the table's own component, so the modal cannot say
   something the row does not. It opens from a click on a row or a card, Enter on a row,
   and the "פרטי משרה" control every record carries; the row's link icon, and this
   modal's primary command, go straight to the work. */
export const ApplicationDetailsDialog = ({
  application,
  clearing,
  onClearNextAction,
  onClose,
  onRequestUpdate,
}: ApplicationDetailsDialogProps) => {
  if (application === null) {
    return null;
  }

  const { step, total } = preparationProgress(application.preparation_state);
  const host = sourceHostname(application.source_url);

  return (
    <Dialog
      footer={
        <>
          <Button
            onClick={() => {
              onClose();
              onRequestUpdate(application);
            }}
            variant="secondary"
          >
            עדכון סטטוס גיוס
          </Button>
          <Button onClick={onClose} variant="secondary">
            סגירה
          </Button>
          <Link className={buttonClasses("primary")} onClick={onClose} to={preparationResumeDestination(application)}>
            המשך בהכנה
          </Link>
        </>
      }
      headingId="application-details-heading"
      onClose={onClose}
      open
      size="wide"
      title={<span dir="auto">פרטי משרה: {application.company}</span>}
    >
      <div className="flex flex-col gap-4">
        <p className="-mt-2 text-support text-cv-text-muted">
          <span className="font-medium text-cv-text" dir="auto">
            {application.target_role}
          </span>
          {application.track == null ? null : ` · ${trackLabel(application.track)}`}
        </p>

        <div className="grid grid-cols-2 gap-3 rounded-control border border-cv-border bg-cv-canvas p-3.5 sm:grid-cols-4">
          <Fact label="סטטוס משרה">{application.is_closed ? "סגורה" : "פתוחה"}</Fact>
          <Fact label="הכנת קו״ח">
            {preparationStateLabels[application.preparation_state]}
            <span className="ms-1 font-normal text-cv-text-muted tabular-nums" dir="ltr">{`${step}/${total}`}</span>
          </Fact>
          <Fact label="שלב גיוס">
            <ApplicationRecruitmentStatus item={application} />
          </Fact>
          <Fact label="ציון התאמה">
            <ApplicationFitStatus item={application} />
          </Fact>
        </div>

        <section aria-label="פעולה מומלצת הבאה" className="rounded-control border border-cv-border bg-cv-surface p-4">
          <p className="mb-1.5 text-support font-semibold text-cv-text-muted">פעולה מומלצת הבאה</p>
          <ApplicationRowNextAction clearing={clearing} item={application} onClearNextAction={onClearNextAction} />
        </section>

        {application.latest_ready_revision_id == null ? null : (
          <ReadyCv onClose={onClose} revisionId={application.latest_ready_revision_id} />
        )}

        {host === null || application.source_url == null ? null : (
          <a
            className="inline-flex w-fit items-center gap-2 text-support font-medium text-cv-accent hover:underline"
            href={application.source_url}
            rel="noreferrer"
            target="_blank"
          >
            <ExternalLink aria-hidden="true" className="size-icon-sm shrink-0" />
            מודעת המשרה המקורית
            <span className="text-cv-text-muted" dir="ltr">
              {host}
            </span>
          </a>
        )}

        {application.notes === "" ? null : (
          <div className="rounded-control border border-cv-border p-3.5">
            <p className="mb-1 text-support text-cv-text-muted">הערות</p>
            <p className="whitespace-pre-wrap text-support leading-relaxed text-cv-text" dir="auto">
              {application.notes}
            </p>
          </div>
        )}

        <p className="border-t border-cv-border pt-3 text-support text-cv-text-muted tabular-nums">
          נוצרה: {formatDateTime(application.created_at, "short")} · עודכנה:{" "}
          {formatDateTime(application.updated_at, "short")}
        </p>
      </div>
    </Dialog>
  );
};
