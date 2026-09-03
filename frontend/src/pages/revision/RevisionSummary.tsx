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
}

export const RevisionSummary = ({ detail, onOpenSubmission, revision }: RevisionSummaryProps) => {
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
                {revision.ready_qualified ? "Ready" : "ממתינה לקבצים תקינים"}
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
          </div>
        </div>

        {recruiterPdfArtifactId == null ? null : (
          <div className="flex flex-wrap items-center gap-2">
            <a className={buttonClasses("primary")} href={recruiterPdfHref(revision.id, recruiterPdfArtifactId)}>
              <Download aria-hidden="true" className="size-4" />
              הורדת PDF
            </a>
            <Button onClick={onOpenSubmission} variant="secondary">
              <Send aria-hidden="true" className="size-4" />
              רישום הגשת הגרסה הזו
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
};
