import { FilePlus2, PencilLine } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import type { ApplicationDetail, ApprovedRevision } from "@/api/contracts";
import { routePaths } from "@/app/routePaths";
import { Button, buttonClasses } from "@/ui/Button";
import { Select } from "@/ui/Select";
import { StatusBadge } from "@/ui/StatusBadge";
import { formatDateTime } from "@/utils/formatDateTime";

interface RevisionSelectorProps {
  currentRevisionId: string;
  detail: ApplicationDetail | undefined;
  onCreateDraft: () => void;
  createPending: boolean;
  revisions: ApprovedRevision[];
  canCreateDraft: boolean;
  submittedAt: string | null;
}

export const RevisionSelector = ({
  canCreateDraft,
  createPending,
  currentRevisionId,
  detail,
  onCreateDraft,
  revisions,
  submittedAt,
}: RevisionSelectorProps) => {
  const navigate = useNavigate();
  const ordered = [...revisions].sort((left, right) => right.version_number - left.version_number);
  const current = ordered.find((revision) => revision.id === currentRevisionId);
  const latestRevisionId = ordered[0]?.id;
  const activeDraft = detail?.active_working_draft_id != null;

  return (
    <section aria-labelledby="revision-history-heading" className="border-b border-cv-border pb-5">
      <h2 className="text-caption font-bold text-cv-text-muted" id="revision-history-heading">
        גרסאות קורות החיים
      </h2>
      <div className="mt-2 flex flex-wrap items-end gap-3">
        <div className="min-w-64 flex-1 sm:max-w-xl">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <label className="sr-only" htmlFor="approved-revision-select">
              הגרסה המוצגת
            </label>
            <div className="min-w-0 flex-1">
              <Select
                aria-label="הגרסה המוצגת"
                className="font-semibold"
                id="approved-revision-select"
                onChange={(event) => navigate(routePaths.revision(event.target.value))}
                value={currentRevisionId}
              >
                {ordered.map((revision) => (
                  <option key={revision.id} value={revision.id}>
                    גרסה {revision.version_number} · {formatDateTime(revision.approved_at, "short")} ·{" "}
                    {revision.ready_qualified ? "מוכנה למסירה" : "ללא קובץ כשיר"}
                  </option>
                ))}
              </Select>
            </div>
            {current === undefined ? null : (
              <StatusBadge tone={current.id === latestRevisionId ? "success" : "neutral"}>
                {current.id === latestRevisionId ? "הגרסה העדכנית" : "גרסה היסטורית"}
              </StatusBadge>
            )}
          </div>
        </div>

        {activeDraft && detail !== undefined ? (
          <Link className={buttonClasses("secondary")} to={routePaths.draft(detail.application.id)}>
            <PencilLine aria-hidden="true" className="size-icon-md" />
            המשך עבודה על הטיוטה החדשה
          </Link>
        ) : canCreateDraft ? (
          <Button onClick={onCreateDraft} pending={createPending} pendingLabel="יוצר טיוטה…" variant="secondary">
            <FilePlus2 aria-hidden="true" className="size-icon-md" />
            יצירת טיוטה חדשה מגרסה {current?.version_number ?? "זו"}
          </Button>
        ) : null}
      </div>
      <p className="mt-2 text-caption leading-5 text-cv-text-muted">
        {current === undefined ? null : <>אושרה {formatDateTime(current.approved_at, "short")}. </>}
        {submittedAt === null ? null : <>הוגשה {formatDateTime(submittedAt, "short")}. </>}
        הבחירה משנה רק את הגרסה המוצגת; גרסאות וקבצים קיימים נשארים ללא שינוי.
      </p>
      {!activeDraft || detail === undefined ? null : (
        <p className="mt-1 text-caption text-cv-text-muted">הטיוטה הפעילה אינה משנה את הגרסה המוצגת עד לאישור.</p>
      )}
      {activeDraft || canCreateDraft ? null : (
        <p className="mt-1 text-caption text-cv-text-muted">
          יצירת טיוטה חדשה תהיה זמינה לאחר השלמת הניתוח ובחירת התוכן הפעילים.
        </p>
      )}
    </section>
  );
};
