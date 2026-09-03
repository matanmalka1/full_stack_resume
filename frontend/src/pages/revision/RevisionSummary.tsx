import { Download, FileCheck2, Send } from "lucide-react";

import type { ApplicationDetail, ApprovedRevision } from "../../api/contracts";
import { recruiterPdfHref } from "../../api/revisions";
import { Button, buttonClasses } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { StatusBadge } from "../../ui/StatusBadge";
import { formatDateTime } from "../../ui/formatDateTime";

interface RevisionSummaryProps {
  detail: ApplicationDetail | undefined;
  onOpenSubmission: () => void;
  revision: ApprovedRevision;
  /* When this exact revision is already on record as submitted, and when. `null` is
     "never submitted", which is the only state in which recording one is the plain next
     action rather than a repeat. */
  submittedAt: string | null;
}

export const RevisionSummary = ({ detail, onOpenSubmission, revision, submittedAt }: RevisionSummaryProps) => {
  const recruiterPdfArtifactId = revision.ready_qualified ? revision.pdf_artifact_version_id : null;

  return (
    <Card aria-labelledby="revision-summary-heading" className="bg-cv-surface p-4 shadow-surface sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-pill bg-cv-success-soft text-cv-success">
            <FileCheck2 aria-hidden="true" className="size-5" />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-heading-sm font-bold text-cv-text" id="revision-summary-heading">
                {revision.ready_qualified ? "גרסה מוכנה למסירה" : "גרסה מאושרת וקבועה"}
              </h2>
              <StatusBadge tone={revision.ready_qualified ? "success" : "warning"}>
                {revision.ready_qualified ? "מוכן למסירה" : "ממתינה לקבצים תקינים"}
              </StatusBadge>
            </div>
            {detail === undefined ? null : (
              <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                {detail.application.company} · {detail.application.target_role}
              </p>
            )}
            <p className="mt-1 text-support text-cv-text-muted">
              אושרה {formatDateTime(revision.approved_at, "short")} · גרסה {revision.version_number}
            </p>
            {submittedAt === null ? null : (
              <p className="mt-1 text-support font-medium text-cv-success">
                הוגשה {formatDateTime(submittedAt, "short")}
              </p>
            )}
          </div>
        </div>

        {recruiterPdfArtifactId == null ? null : (
          <div className="flex flex-wrap items-center gap-2">
            <a className={buttonClasses("primary")} href={recruiterPdfHref(revision.id, recruiterPdfArtifactId)}>
              <Download aria-hidden="true" className="size-4" />
              הורדת PDF
            </a>
            {/* The button says what pressing it would do next, which is not the same
                sentence once a submission is on record. It stayed "רישום הגשת הגרסה הזו"
                after the submission was recorded, so the screen offered the action it had
                just completed as though nothing had happened. */}
            <Button onClick={onOpenSubmission} variant={submittedAt === null ? "secondary" : "ghost"}>
              <Send aria-hidden="true" className="size-4" />
              {submittedAt === null ? "רישום הגשת הגרסה הזו" : "רישום הגשה נוספת"}
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
};
