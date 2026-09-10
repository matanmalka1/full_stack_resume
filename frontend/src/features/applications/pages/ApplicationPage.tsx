import { useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

import { applicationDetailQueryOptions } from "@/api/applications";
import type { ProblemDetails } from "@/api/client";
import { useRequiredParam } from "@/app/useRequiredParam";
import { useWatchedOperation } from "@/features/operations";
import { Callout } from "@/ui/Callout";
import { Disclosure } from "@/ui/Disclosure";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { ActiveOperationPanel, PendingWorkCard, operationTypeLabels } from "@/features/operations";
import { PreparationView, WizardStepShell, useAutomaticDraft } from "@/features/preparation";
import { applicationLabel } from "../model/applicationPresentation";
import { analysisViewState } from "../model/analysisViewState";
import { ApplicationArtifacts } from "../components/ApplicationArtifacts";
import { JobSnapshotPanel } from "../components/JobSnapshotPanel";

/* The news that an Application was just created, handed over in route state by the intake
   screen. It is the one thing on this page that is not read from the projection, because
   it is about the request that made the record rather than about the record. */
interface CreatedApplicationState {
  analysisProblem?: ProblemDetails | null;
  analysisQueued?: unknown;
}

/* The wait before this screen holds an Operation to report, in the one shape every later
   moment of the same work is reported in.

   Two guards can reach it - the projection not yet resolved, and resolved with the watch
   not yet opened - and they are two moments of one fact, so they render one card from one
   copy rather than each writing its own line of text. */
const analysisPending = (
  <PendingWorkCard
    /* The heading the panel that replaces this will carry, from the same table, so the
       card keeps its title through the swap instead of renaming itself. */
    heading={<>הרצת {operationTypeLabels.analyze_job}</>}
    note="יוצרים את המועמדות ומנתחים את המשרה…"
  />
);

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

  const { continuation } = useAutomaticDraft({
    applicationId,
    detail,
    operation: watched,
    operationId: watchedId,
    watch,
  });

  const createdApplication = (location.state as { createdApplication?: CreatedApplicationState } | null)
    ?.createdApplication;
  const viewState = analysisViewState({
    analysisWasQueuedOnCreate: createdApplication?.analysisQueued === true,
    detail,
    operation: watched,
  });

  /* The files exist only after a revision is rendered, so their reference section is drawn
     only once there is something in it - never as an empty disclosure the reader opens onto
     nothing. */
  const hasArtifacts = detail !== undefined && detail.latest_ready_revision_id != null;

  return (
    /* The analysis step of the wizard. Its name, its spine and its measure are the shell's;
       what is left here is the one thing this step is identified by - who the CV is for.
       The heading used to be the target role, which named the record rather than the step
       and left the reader's position stated only by the rail. */
    <WizardStepShell
      applicationId={applicationId}
      detail={detail}
      /* Held at one line's width while the projection is in flight. Absent, the masthead
         drew the heading a line higher and dropped it when the name arrived - the page's
         own title moving under the reader as the first thing it did. */
      eyebrow={
        detail === undefined ? (
          <Skeleton className="inline-block w-56 max-w-full align-middle" />
        ) : (
          <span dir="auto">{applicationLabel(detail.application.company, detail.application.target_role)}</span>
        )
      }
      stage="analysis"
    >
      <QueryState
        error={query.error}
        fallbackTitle="לא ניתן לטעון את פרטי המועמדות"
        loading={detail === undefined}
        loadingLabel="טוען את פרטי המועמדות…"
        loadingState={viewState === "processing" ? analysisPending : undefined}
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

            {/* Analysis work and preparation content are mutually exclusive product
                states. The projection can still say `needs_analysis` for a poll after
                the Operation starts (and after it succeeds); rendering both exposed the
                internal state machine as a flash of an obsolete call to action. One
                Operation panel call site covers every viewState - it is the same report
                whether analysis is still running or already history. */}
            {(viewState === "processing" || viewState === "analysis_failed") && watched === undefined
              ? analysisPending
              : null}
            {watched === undefined ? null : (
              <ActiveOperationPanel continuation={continuation} onQueued={watch} operation={watched} />
            )}
            {viewState === "content" ? <PreparationView detail={detail} onQueued={watch} /> : null}

            {/* The posting the CV is tailored to, and the files the work produced: reference
                the reader checks or downloads, folded away so the step above stays the
                screen's subject.

                Behind a rule and a quiet heading, because a drawer sitting in the same
                column at the same weight as the step reads as another panel of it - which
                is how a step turns back into a record with sections. The line says where
                the step ends and the material about it begins. */}
            {viewState === "content" ? (
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
            ) : null}
          </div>
        )}
      </QueryState>
    </WizardStepShell>
  );
};
