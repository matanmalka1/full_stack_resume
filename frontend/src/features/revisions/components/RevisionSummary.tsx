import { FileCheck2 } from "lucide-react";

import type { ApplicationDetail, ApprovedRevision } from "@/api/contracts";
import { Card } from "@/ui/Card";
import { StatusBadge } from "@/ui/StatusBadge";
import { formatDateTime } from "@/utils/formatDateTime";
import { applicationLabel } from "@/features/applications";

interface RevisionSummaryProps {
  detail: ApplicationDetail | undefined;
  revision: ApprovedRevision;
  /* When this exact revision is already on record as submitted, and when. `null` is
     "never submitted", which is the only state in which recording one is the plain next
     action rather than a repeat. */
  submittedAt: string | null;
}

/* What this revision is, and nothing about what to do with it.

   The download and the submission used to sit in this card's own corner, which put the
   step's actions in a third place: the preparation step ends with an action bar, the
   editor pins its approval, and the ready step hid its two commands inside an identity
   card beside the company name. They are on the step's `CommitBar` now, where the other
   two steps put theirs. What is left here is the record: which revision, approved when, and whether
   it already went out. */
export const RevisionSummary = ({ detail, revision, submittedAt }: RevisionSummaryProps) => {
  return (
    <Card aria-labelledby="revision-summary-heading" className="bg-cv-surface p-4 shadow-surface sm:p-5">
      {/* Two sides, because the card is as wide as the step is. What the revision is
          reads from the opening edge; when it happened is a second, smaller column at the
          closing one. Stacked into a single left-hand block they left most of a
          full-width card empty and the dates trailing under the company name as though
          they were part of it. Below `sm` the row wraps and the old stack returns. */}
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="grid size-11 shrink-0 place-items-center rounded-pill bg-cv-success-soft text-cv-success">
            <FileCheck2 aria-hidden="true" className="size-icon-lg" />
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
                {applicationLabel(detail.application.company, detail.application.target_role)}
              </p>
            )}
          </div>
        </div>

        <div className="min-w-0 shrink-0">
          <p className="text-support text-cv-text-muted">
            אושרה {formatDateTime(revision.approved_at, "short")} · גרסה {revision.version_number}
          </p>
          {submittedAt === null ? null : (
            <p className="mt-1 text-support font-medium text-cv-success">
              הוגשה {formatDateTime(submittedAt, "short")}
            </p>
          )}
        </div>
      </div>
    </Card>
  );
};
