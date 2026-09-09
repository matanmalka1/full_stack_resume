import { useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

import { applicationDetailQueryOptions } from "@/api/applications";
import type { ProblemDetails } from "@/api/client";
import { useRequiredParam } from "@/app/useRequiredParam";
import { useWatchedOperation } from "@/features/operations";
import { Callout } from "@/ui/Callout";
import { Disclosure } from "@/ui/Disclosure";
import { PageShell } from "@/ui/PageShell";
import { QueryState } from "@/ui/QueryState";
import { ActiveOperationPanel } from "@/features/operations";
import { PreparationView, PreparationWorkflowSteps, useAutomaticDraft } from "@/features/preparation";
import { applicationLabel } from "../model/applicationPresentation";
import { ApplicationArtifacts } from "../components/ApplicationArtifacts";
import { JobSnapshotPanel } from "../components/JobSnapshotPanel";

/* The news that an Application was just created, handed over in route state by the intake
   screen. It is the one thing on this page that is not read from the projection, because
   it is about the request that made the record rather than about the record. */
interface CreatedApplicationState {
  analysisProblem?: ProblemDetails | null;
  analysisQueued?: unknown;
}

/* One step of the workflow wizard for one Application: preparing its CV.

   Not a record you browse. The screen used to be a hub of tabs - decisions, facts and the
   diagnosis under one tab bar, the posting and the files under another, a two-axis state
   panel and a recruitment column above them all - several readings of one projection side
   by side. A wizard shows the step, not the record: the progress spine says where the work
   stands across analysis, draft and ready; `PreparationView` is the one action the step is
   waiting on with its supporting detail folded away; and the posting and the files sit
   below as reference a press away, never as panels competing for the same space.

   Recruitment is not here at all. Where the application stands with the employer moves on
   its own axis and is managed from the board; putting it beside the CV work claimed a
   relationship between the two that does not exist and crowded the one task this screen is
   for. */
export const ApplicationPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const location = useLocation();

  const query = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = query.data;
  const { operation: watched, watch, operationId: watchedId } = useWatchedOperation(applicationId, detail);

  useAutomaticDraft({
    applicationId,
    detail,
    operation: watched,
    operationId: watchedId,
    watch,
  });

  const createdApplication = (location.state as { createdApplication?: CreatedApplicationState } | null)
    ?.createdApplication;

  /* The files exist only after a revision is rendered, so their reference section is drawn
     only once there is something in it - never as an empty disclosure the reader opens onto
     nothing. */
  const hasArtifacts = detail !== undefined && detail.latest_ready_revision_id != null;

  return (
    <PageShell
      eyebrow={
        detail === undefined ? undefined : (
          <span dir="auto">{applicationLabel(detail.application.company, detail.application.target_role)}</span>
        )
      }
      landmark={<PreparationWorkflowSteps applicationId={applicationId} detail={detail} />}
      measure="wizard"
      /* The step's name, the same word the spine above uses for it. The heading used to
         be the target role, which named the record rather than the step and left the
         reader's position stated only by the rail. The role and company are the eyebrow,
         where identity belongs on a screen that is one step of a longer piece of work. */
      title="ניתוח והתאמה"
    >
      <QueryState
        error={query.error}
        fallbackTitle="לא ניתן לטעון את פרטי המועמדות"
        loading={detail === undefined}
        loadingLabel="טוען את פרטי המועמדות…"
      >
        {detail === undefined ? null : (
          <div className="space-y-6">
            {/* A successfully queued analysis is reported by the Operation panel below,
                which follows the run through its current and terminal states. Route state
                only owns the exceptional creation outcome where no Operation exists to
                report; keeping its success message would freeze "running" beside the
                Operation's later "completed" state. */}
            {createdApplication?.analysisQueued !== false ? null : (
              <Callout role="alert" title="המועמדות נוצרה, אך הניתוח לא הופעל" tone="warning">
                {createdApplication.analysisProblem?.detail ?? "ניתן להפעיל את הניתוח מהמסך הזה."} המועמדות שכבר נוצרה
                לא תיווצר שוב.
              </Callout>
            )}

            {/* Live work, reported once above the step it belongs to. */}
            {watched === undefined ? null : <ActiveOperationPanel onQueued={watch} operation={watched} />}

            <PreparationView detail={detail} onQueued={watch} />

            {/* The posting the CV is tailored to, and the files the work produced: reference
                the reader checks or downloads, folded away so the step above stays the
                screen's subject.

                Behind a rule and a quiet heading, because a drawer sitting in the same
                column at the same weight as the step reads as another panel of it - which
                is how a step turns back into a record with sections. The line says where
                the step ends and the material about it begins. */}
            <div className="flex flex-col gap-2 border-t border-cv-border pt-5">
              <p className="text-support font-semibold text-cv-text-muted">חומר עזר</p>

              <Disclosure summary="צפייה בנוסח המשרה שנשמר">
                <div className="pt-2">
                  <JobSnapshotPanel detail={detail} />
                </div>
              </Disclosure>

              {hasArtifacts ? (
                <Disclosure summary="גרסאות וקבצים">
                  <div className="pt-2">
                    <ApplicationArtifacts applicationId={applicationId} />
                  </div>
                </Disclosure>
              ) : null}
            </div>
          </div>
        )}
      </QueryState>
    </PageShell>
  );
};
