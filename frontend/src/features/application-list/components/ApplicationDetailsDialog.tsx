import { Download, ExternalLink, FileCheck2 } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { documentPdfHref } from "@/api/documents";
import { routePaths } from "@/app/routePaths";
import { sourceHostname } from "@/features/applications";
import { preparationResumeDestination, preparationStateLabels, trackLabel } from "@/features/preparation";
import { Button, buttonClasses } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { formatDateTime } from "@/utils/formatDateTime";
import { applicationAttention, preparationProgress } from "../model/applicationListPresentation";
import { ApplicationFitStatus, ApplicationRecruitmentStatus } from "./ApplicationListStatuses";
import { ApplicationCardNextAction, nextActionHeading } from "./ApplicationCardNextAction";

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

/* The finished CV and its PDF, as demo_re offers them. The board's list item already says
   the document is Ready and carries its hash, so the download is the document's own PDF -
   which the server refuses unless the document is still Ready when it answers. The link to
   the ready step is drawn only when the footer's primary command is not already that link. */
const ReadyCv = ({
  applicationId,
  documentHash,
  linkToReady,
  onClose,
}: {
  applicationId: string;
  documentHash: string;
  linkToReady: boolean;
  onClose: () => void;
}) => (
  <div className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-cv-border p-3.5">
    <span className="inline-flex items-center gap-2 text-support font-medium text-cv-text">
      <FileCheck2 aria-hidden="true" className="size-icon-md shrink-0 text-cv-text-muted" />
      קורות חיים מוכנים למשרה זו
    </span>
    <span className="flex flex-wrap items-center gap-2">
      {linkToReady ? (
        <Link
          className={buttonClasses("secondary", undefined, "compact")}
          onClick={onClose}
          to={routePaths.ready(applicationId)}
        >
          פתיחת קורות החיים המוכנים
        </Link>
      ) : null}
      <a
        className={buttonClasses("secondary", undefined, "compact")}
        href={documentPdfHref(applicationId, documentHash)}
      >
        <Download aria-hidden="true" className="size-icon-sm" />
        הורדת PDF
      </a>
    </span>
  </div>
);

/* A timestamp as its own left-to-right island, so the date and time keep their order
   inside the Hebrew sentence instead of the comma flipping them. */
const Stamp = ({ value }: { value: string }) => <bdi dir="ltr">{formatDateTime(value, "short")}</bdi>;

/* One Application at a glance, laid out after demo_re's job-details modal: who, its
   four states side by side, the one thing to do next, the finished CV, the posting, the
   reader's notes and when it was opened and last changed.

   Each fact is said once. The finished CV has its own block, so the next-action block
   leaves it out, and the block does not repeat the ready link when the footer's
   primary command already goes there. The dialog's own
   close control and Escape close it; the footer holds only the two ways onward.

   It is read from the board's own list item alone, and every block is the card's own component, so the modal cannot say
   something the card does not. It opens from a click on a card and from the "פרטי משרה"
   control every record carries. */
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
  const readyHash = application.document_state === "ready" ? (application.document_hash ?? null) : null;
  const continuesToReady = readyHash !== null && destination === routePaths.ready(application.id);
  /* The finished CV has its own block below, so the next-action block reads the record
     as if it had none: it then names only a run, a recommended step or the reminder,
     and never a second "the CV is ready" or a second link to it. */
  const withoutReadyCv: ApplicationListItem = {
    ...application,
    document_state: application.document_state === "ready" ? "approved" : application.document_state,
  };
  const hasNextStep = nextActionHeading(withoutReadyCv, applicationAttention(application) !== null) !== null;

  const description = (
    <>
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
    </>
  );

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
            {continuesToReady ? "פתיחת קורות החיים המוכנים" : "המשך בהכנה"}
          </Link>
        </>
      }
      description={description}
      headingId="application-details-heading"
      onClose={onClose}
      open
      size="wide"
      title={<span dir="auto">פרטי משרה: {application.company}</span>}
    >
      <div className="flex flex-col gap-4">
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
            <ApplicationCardNextAction
              clearing={clearing}
              item={withoutReadyCv}
              onClearNextAction={onClearNextAction}
            />
          </section>
        ) : null}

        {readyHash === null ? null : (
          <ReadyCv
            applicationId={application.id}
            documentHash={readyHash}
            linkToReady={!continuesToReady}
            onClose={onClose}
          />
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
