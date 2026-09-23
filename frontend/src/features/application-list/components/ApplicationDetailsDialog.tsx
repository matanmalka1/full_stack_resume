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
import { applicationAttention, preparationProgress } from "../model/applicationListPresentation";
import { ApplicationFitStatus, ApplicationRecruitmentStatus } from "./ApplicationListStatuses";
import { ApplicationRowNextAction, nextActionHeading } from "./ApplicationRowNextAction";

interface ApplicationDetailsDialogProps {
  application: ApplicationListItem | null;
  clearing: boolean;
  onClearNextAction: (item: ApplicationListItem) => void;
  onClose: () => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

const Fact = ({ children, detail, label }: { children: ReactNode; detail?: ReactNode; label: string }) => (
  <div className="flex min-w-0 flex-col items-start gap-1">
    <span className="text-support text-cv-text-muted">{label}</span>
    <span className="text-support font-semibold text-cv-text">{children}</span>
    {detail === undefined ? null : <span className="text-support text-cv-text-muted tabular-nums">{detail}</span>}
  </div>
);

/* The finished CV and its PDF, as demo_re offers them. The board row names only the
   revision, so the PDF's artifact comes from the revision itself - the same read, and
   the same recruiter-pdf delivery, the revision screen uses. A revision that did not
   qualify, or whose read has not arrived, offers no download. The link to the revision
   is drawn only when the footer's primary command is not already that link. */
const ReadyCv = ({
  linkToRevision,
  onClose,
  revisionId,
}: {
  linkToRevision: boolean;
  onClose: () => void;
  revisionId: string;
}) => {
  const revision = useQuery(approvedRevisionQueryOptions(revisionId)).data;
  const pdfArtifactId = revision?.ready_qualified === true ? (revision.pdf_artifact_version_id ?? null) : null;

  if (!linkToRevision && pdfArtifactId === null) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-cv-border p-3.5">
      <span className="inline-flex items-center gap-2 text-support font-medium text-cv-text">
        <FileCheck2 aria-hidden="true" className="size-icon-md shrink-0 text-cv-text-muted" />
        קורות חיים מוכנים למשרה זו
      </span>
      <span className="flex flex-wrap items-center gap-2">
        {linkToRevision ? (
          <Link
            className={buttonClasses("secondary", undefined, "compact")}
            onClick={onClose}
            to={routePaths.revision(revisionId)}
          >
            פתיחת הגרסה המוכנה
          </Link>
        ) : null}
        {pdfArtifactId === null ? null : (
          <a
            className={buttonClasses("secondary", undefined, "compact")}
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

/* A timestamp as its own left-to-right island, so the date and time keep their order
   inside the Hebrew sentence instead of the comma flipping them. */
const Stamp = ({ value }: { value: string }) => <bdi dir="ltr">{formatDateTime(value, "short")}</bdi>;

/* One Application at a glance, laid out after demo_re's job-details modal: who, its
   four states side by side, the one thing to do next, the finished CV, the posting, the
   reader's notes and when it was opened and last changed.

   Each fact is said once. The finished CV has its own block, so the next-action block
   leaves it out, and the block does not repeat the revision link when the footer's
   primary command already goes there. The dialog's own
   close control and Escape close it; the footer holds only the two ways onward.

   It is read from the board's own row - only a finished CV's revision is fetched, for
   its PDF - and every block is the table's own component, so the modal cannot say
   something the row does not. It opens from a click on a row or a card, Enter on a row,
   and the "פרטי משרה" control every record carries. */
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
  const destination = preparationResumeDestination(application);
  const readyRevisionId = application.latest_ready_revision_id ?? null;
  const continuesToRevision = readyRevisionId !== null && destination === routePaths.revision(readyRevisionId);
  /* The finished CV has its own block below, so the next-action block reads the record
     as if it had none: it then names only a run, a recommended step or the reminder,
     and never a second "the CV is ready" or a second link to it. */
  const withoutReadyCv: ApplicationListItem = { ...application, latest_ready_revision_id: null };
  const hasNextStep = nextActionHeading(withoutReadyCv, applicationAttention(application) !== null) !== null;

  return (
    <Dialog
      footer={
        <>
          <Button
            className="me-auto"
            onClick={() => {
              onClose();
              onRequestUpdate(application);
            }}
            variant="secondary"
          >
            עדכון סטטוס גיוס
          </Button>
          <Link className={buttonClasses("primary")} onClick={onClose} to={destination}>
            {continuesToRevision ? "פתיחת הגרסה המוכנה" : "המשך בהכנה"}
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
        <p className="text-support text-cv-text-muted">
          <span className="font-medium text-cv-text" dir="auto">
            {application.target_role}
          </span>
          {application.track == null ? null : ` · ${trackLabel(application.track)}`}
          {host === null || application.source_url == null ? null : (
            <>
              {" · "}
              <a
                className="inline-flex items-center gap-1 text-cv-accent hover:underline"
                href={application.source_url}
                rel="noreferrer"
                target="_blank"
              >
                מודעת המשרה
                <ExternalLink aria-hidden="true" className="size-icon-sm" />
              </a>
            </>
          )}
        </p>

        <div className="grid grid-cols-2 gap-4 rounded-control border border-cv-border bg-cv-canvas p-4 sm:grid-cols-4">
          <Fact label="סטטוס משרה">{application.is_closed ? "סגורה" : "פתוחה"}</Fact>
          <Fact detail={`שלב ${step} מתוך ${total}`} label="הכנת קו״ח">
            {preparationStateLabels[application.preparation_state]}
          </Fact>
          <Fact label="שלב גיוס">
            <ApplicationRecruitmentStatus item={application} />
          </Fact>
          <Fact label="ציון התאמה">
            <ApplicationFitStatus item={application} />
          </Fact>
        </div>

        {hasNextStep ? (
          <section aria-label="פעולה מומלצת הבאה" className="rounded-control border border-cv-border p-4">
            <p className="mb-1.5 text-support font-semibold text-cv-text-muted">פעולה מומלצת הבאה</p>
            <ApplicationRowNextAction clearing={clearing} item={withoutReadyCv} onClearNextAction={onClearNextAction} />
          </section>
        ) : null}

        {readyRevisionId === null ? null : (
          <ReadyCv linkToRevision={!continuesToRevision} onClose={onClose} revisionId={readyRevisionId} />
        )}

        {application.notes === "" ? null : (
          <div className="rounded-control border border-cv-border p-4">
            <p className="mb-1 text-support font-semibold text-cv-text-muted">הערות</p>
            <p className="whitespace-pre-wrap text-support leading-relaxed text-cv-text" dir="auto">
              {application.notes}
            </p>
          </div>
        )}

        <p className="text-support text-cv-text-muted tabular-nums">
          נוצרה <Stamp value={application.created_at} /> · עודכנה <Stamp value={application.updated_at} />
        </p>
      </div>
    </Dialog>
  );
};
