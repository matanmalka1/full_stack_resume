import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { applicationDetailQueryOptions } from "../api/applications";
import type { ApplicationDetail } from "../api/contracts";
import { useWorkflowStage, workflowDestinations } from "../app/WorkflowLandmark";
import { buttonClasses } from "../ui/Button";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { StatusBadge } from "../ui/StatusBadge";
import { SummaryList } from "../ui/SummaryList";
import { dateTimesMatch, formatDateTime } from "../ui/formatDateTime";
import { ApplicationSectionNav } from "./ApplicationSectionNav";
import { ArtifactsPanel } from "./application/ArtifactsPanel";
import { JobSnapshotPanel } from "./application/JobSnapshotPanel";
import {
  draftStateIsImplied,
  preparationStateLabels,
  preparationStateTones,
  recruitmentStatusIcon,
  recruitmentStatusLabel,
  recruitmentStatusTone,
  workingDraftStateLabels,
  workingDraftStateTones,
} from "./application/applicationLabels";
import { RecruitmentPanel } from "./recruitment/RecruitmentPanel";

const sourceLabel = (source: string): string => (source === "manual" ? "הזנה ידנית" : source);

/* Job Detail owns the job and recruitment facts. Preparation is represented here only
   by its server-owned projection and a link to the workflow that can change it. */
const JobOverview = ({ detail }: { detail: ApplicationDetail }) => {
  const application = detail.application;

  return (
    <section aria-labelledby="job-overview-heading">
      <h2 className="text-body font-semibold text-cv-text" id="job-overview-heading">
        פרטי המועמדות
      </h2>
      <div className="mt-4">
        <SummaryList
          items={[
            { term: "מקור המועמדות", value: sourceLabel(application.source) },
            ...(detail.terminal_outcome == null
              ? []
              : [{ term: "תוצאת התהליך", value: recruitmentStatusLabel(detail.terminal_outcome) }]),
            ...(application.last_contact_date == null
              ? []
              : [{ term: "קשר אחרון", value: formatDateTime(application.last_contact_date) }]),
            { term: "נוצרה", value: formatDateTime(application.created_at) },
            ...(dateTimesMatch(application.created_at, application.updated_at)
              ? []
              : [{ term: "עודכנה לאחרונה", value: formatDateTime(application.updated_at) }]),
          ]}
        />
      </div>
      {application.notes.trim() === "" ? null : (
        <div className="mt-4 border-t border-cv-border pt-4">
          <h3 className="text-support font-semibold text-cv-text">הערות</h3>
          <p className="mt-2 whitespace-pre-wrap text-support leading-6 text-cv-text-muted" dir="auto">
            {application.notes}
          </p>
        </div>
      )}
    </section>
  );
};

const PreparationSummary = ({ detail }: { detail: ApplicationDetail }) => (
  <section aria-labelledby="preparation-summary-heading">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 className="text-body font-semibold text-cv-text" id="preparation-summary-heading">
          מצב הכנת קורות החיים
        </h2>
        <div className="mt-3 flex flex-wrap gap-2">
          <StatusBadge tone={preparationStateTones[detail.preparation_state]}>
            {preparationStateLabels[detail.preparation_state]}
          </StatusBadge>
          {draftStateIsImplied(detail) ? null : (
            <StatusBadge tone={workingDraftStateTones[detail.working_draft_state]}>
              {workingDraftStateLabels[detail.working_draft_state]}
            </StatusBadge>
          )}
        </div>
      </div>
      {detail.latest_ready_revision_id == null && detail.active_working_draft_id == null ? null : (
        <div className="flex flex-wrap gap-2">
          {detail.latest_ready_revision_id == null ? null : (
            <Link
              className={buttonClasses("ghost")}
              to={`/revisions/${encodeURIComponent(detail.latest_ready_revision_id)}`}
            >
              פתיחת הגרסה המוכנה
            </Link>
          )}
          {detail.active_working_draft_id == null ? null : (
            <Link
              className={buttonClasses("ghost")}
              to={`/applications/${encodeURIComponent(detail.application.id)}/draft`}
            >
              פתיחת עורך קורות החיים
            </Link>
          )}
        </div>
      )}
    </div>
  </section>
);

export const JobDetailsPage = () => {
  const { applicationId } = useParams();

  if (applicationId === undefined) {
    throw new Error("JobDetailsPage rendered without an applicationId route parameter");
  }

  const query = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = query.data;

  /* Job Detail said `none` while it was a screen the landmark could not link to. Now that
     intake resolves here, staying silent meant the one destination the bar offers is also
     the one place the bar disappears. It is an Application screen and reports its stage
     like the others; `intake` drops out on its own, being this very path. */
  useWorkflowStage(
    detail === undefined ? "unknown" : detail.preparation_state,
    workflowDestinations(applicationId, detail),
  );

  return (
    <PageShell
      actions={
        detail === undefined ? null : (
          <StatusBadge
            icon={recruitmentStatusIcon(detail.recruitment_status)}
            tone={recruitmentStatusTone(detail.recruitment_status)}
          >
            {recruitmentStatusLabel(detail.recruitment_status)}
          </StatusBadge>
        )
      }
      navigation={<ApplicationSectionNav applicationId={applicationId} value="details" />}
      eyebrow={detail === undefined ? undefined : <span dir="auto">{detail.application.company}</span>}
      title={detail?.application.target_role ?? "פרטי משרה"}
      width="detail"
    >
      <QueryState
        error={query.error}
        fallbackTitle="לא ניתן לטעון את פרטי המשרה"
        loading={detail === undefined}
        loadingLabel="טוען את פרטי המשרה…"
      >
        {detail === undefined ? null : (
          <div className="flex flex-col divide-y divide-cv-border [&>section]:py-6 [&>section:first-child]:pt-0 [&>section:last-child]:pb-0">
            <JobOverview detail={detail} />
            <JobSnapshotPanel detail={detail} />
            <PreparationSummary detail={detail} />
            <RecruitmentPanel detail={detail} />
            <ArtifactsPanel applicationId={applicationId} />
          </div>
        )}
      </QueryState>
    </PageShell>
  );
};
