import { useQuery } from "@tanstack/react-query";
import { FileCheck2 } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { applicationDetailQueryOptions } from "../api/applications";
import type { ProblemDetails } from "../api/client";
import type { ApplicationDetail } from "../api/contracts";
import { appRoutes } from "../app/appRoutes";
import { useRequiredParam } from "../app/useRequiredParam";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { useWatchedOperation } from "../hooks/useWatchedOperation";
import { BackLink } from "../ui/BackLink";
import { buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { StatusBadge } from "../ui/StatusBadge";
import { SummaryList } from "../ui/SummaryList";
import { dateTimesMatch, formatDateTime } from "../ui/formatDateTime";
import { ActiveOperationPanel } from "./ActiveOperationPanel";
import { ArtifactsPanel } from "./application/ArtifactsPanel";
import { ApplicationNotes } from "./application/ApplicationNotes";
import { JobSnapshotPanel } from "./application/JobSnapshotPanel";
import { PreparationStatusBadges } from "./application/PreparationStatusBadges";
import { recruitmentStatusIcon, recruitmentStatusLabel, recruitmentStatusTone } from "./application/applicationLabels";
import { RecruitmentPanel } from "./recruitment/RecruitmentPanel";

const sourceLabel = (source: string): string => (source === "manual" ? "הזנה ידנית" : source);

/* Job Detail owns the job and recruitment facts. It is the entrance to an Application,
   not a stage of the CV workflow: the job record is what the reader opens on the day
   they apply and on the day they hear back, long after the document is done. Preparation
   is represented here only by its server-owned projection and the door into it. */
const JobOverview = ({ detail }: { detail: ApplicationDetail }) => {
  const application = detail.application;

  return (
    <Card aria-labelledby="job-overview-heading" className="bg-cv-surface p-4 shadow-surface sm:p-5">
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
      <ApplicationNotes detail={detail} />
    </Card>
  );
};

/* The one door on this screen, and the only place the two halves of an Application meet.

   It is a surface of its own above the job's own sections rather than a fourth section
   among them: preparation is not another fact about the job, it is the work started from
   here, and the screen should say where that work stands and how to reach it before it
   starts listing what the job is. The accent rail is the single loud thing on the page;
   everything below it stays plain. */
const PreparationGate = ({ detail }: { detail: ApplicationDetail }) => {
  const applicationId = detail.application.id;

  return (
    <Card
      aria-labelledby="preparation-gate-heading"
      className="relative overflow-hidden bg-cv-surface-muted p-4 shadow-inner sm:p-5"
    >
      <span aria-hidden="true" className="absolute inset-y-0 start-0 w-1 bg-cv-accent" />
      <div className="flex flex-wrap items-start justify-between gap-4 ps-2">
        <div className="min-w-0">
          <h2 className="text-body font-semibold text-cv-text" id="preparation-gate-heading">
            הכנת קורות החיים
          </h2>
          {/* Says how far the door leads, in the same count the landmark keeps on the
              other side of it. This screen draws no landmark: it is not one of the four. */}
          <p className="mt-1 text-support text-cv-text-muted">
            תהליך נפרד בארבעה שלבים, מניתוח המשרה ועד גרסה מוכנה לשליחה.
          </p>
          <PreparationStatusBadges className="mt-3 flex flex-wrap gap-2" detail={detail} />
        </div>
        <div className="flex flex-wrap gap-2">
          {detail.latest_ready_revision_id == null ? null : (
            <Link className={buttonClasses("primary")} to={appRoutes.revision(detail.latest_ready_revision_id)}>
              <FileCheck2 aria-hidden="true" className="size-4" />
              צפייה בגרסה המוכנה
            </Link>
          )}
          <Link
            className={buttonClasses(detail.latest_ready_revision_id == null ? "primary" : "secondary")}
            to={appRoutes.preparation(applicationId)}
          >
            מעבר להכנת קורות החיים
          </Link>
          {detail.active_working_draft_id == null ? null : (
            <Link className={buttonClasses("ghost")} to={appRoutes.draft(applicationId)}>
              פתיחת עורך קורות החיים
            </Link>
          )}
        </div>
      </div>
    </Card>
  );
};

export const JobDetailsPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const location = useLocation();

  const query = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = query.data;
  const { operation: watched, watch } = useWatchedOperation(applicationId, detail);
  const createdApplication = (
    location.state as {
      createdApplication?: {
        analysisProblem?: ProblemDetails | null;
        analysisQueued?: unknown;
      };
    } | null
  )?.createdApplication;

  /* No stage. The job record is the entrance to an Application and outlives the document
     workflow run against it, so showing the four CV stages here made a screen that is
     never "done" report progress through a process it takes no part in. The door below
     names where preparation stands; the landmark belongs to the screens that do the
     work. */
  useWorkflowStage("none");

  return (
    <PageShell
      actions={
        detail === undefined ? null : (
          <div className="flex flex-wrap items-center justify-end gap-2">
            <StatusBadge
              icon={recruitmentStatusIcon(detail.recruitment_status)}
              tone={recruitmentStatusTone(detail.recruitment_status)}
            >
              {recruitmentStatusLabel(detail.recruitment_status)}
            </StatusBadge>
            <a className={buttonClasses("primary")} href="#recruitment-heading">
              עדכון מעקב הגיוס
            </a>
          </div>
        )
      }
      navigation={
        <BackLink label="חזרה ללוח המועמדויות" to={appRoutes.home}>
          לוח המועמדויות
        </BackLink>
      }
      eyebrow={detail === undefined ? undefined : <span dir="auto">{detail.application.company}</span>}
      title={detail?.application.target_role ?? "פרטי משרה"}
    >
      <QueryState
        error={query.error}
        fallbackTitle="לא ניתן לטעון את פרטי המשרה"
        loading={detail === undefined}
        loadingLabel="טוען את פרטי המשרה…"
      >
        {detail === undefined ? null : (
          <>
            {createdApplication === undefined ? null : createdApplication.analysisQueued === true ? (
              watched === undefined ? (
                <Callout role="status" title="המועמדות נוצרה, הניתוח רץ" tone="progress" />
              ) : (
                <ActiveOperationPanel onQueued={watch} operation={watched} />
              )
            ) : (
              /* No action of its own: the door below is the way to preparation, and two
                 controls with the same destination one above the other made the reader
                 choose between identical doors. */
              <Callout role="alert" title="המועמדות נוצרה, אך הניתוח לא הופעל" tone="warning">
                {createdApplication.analysisProblem?.detail ??
                  "ניתן להפעיל את הניתוח ממסך הכנת קורות החיים."}{" "}
                המועמדות שכבר נוצרה לא תיווצר שוב.
              </Callout>
            )}
            <PreparationGate detail={detail} />
            <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
              <div className="flex min-w-0 flex-col gap-6">
                <JobOverview detail={detail} />
                <RecruitmentPanel detail={detail} />
              </div>
              <div className="min-w-0 lg:self-start">
                <JobSnapshotPanel detail={detail} />
              </div>
              <div className="min-w-0 lg:col-span-2">
                <ArtifactsPanel applicationId={applicationId} />
              </div>
            </div>
          </>
        )}
      </QueryState>
    </PageShell>
  );
};
