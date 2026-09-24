import { useQuery } from "@tanstack/react-query";
import { useLayoutEffect } from "react";
import { useLocation } from "react-router-dom";

import { applicationDetailQueryOptions } from "@/api/applications";
import type { ProblemDetails } from "@/api/client";
import { aiRegenerationAvailable } from "@/api/settings";
import { useSettings } from "@/api/useSettings";
import { useRequiredParam } from "@/app/useRequiredParam";
import { Callout } from "@/ui/Callout";
import { Disclosure } from "@/ui/Disclosure";
import { QueryState } from "@/ui/QueryState";
import { WideRow } from "@/ui/WideRow";
import { LiveRegion } from "@/ui/LiveRegion";
import { Skeleton } from "@/ui/Skeleton";
import {
  OperationOverlay,
  type PendingWork,
  isOperationLive,
  operationTypeLabels,
  useWatchedOperation,
} from "@/features/operations";
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
  /* Intake did not request analysis because no AI provider exists; the step's own banner
     says so and where to fix it, so the "was not started" warning is not repeated. */
  analysisSkipped?: boolean;
  operationId?: string | null;
}

/* The step at its own size while the record is read: the verdict banner it opens with,
   and the collapsed rows under it. The screen is linked to directly from the board, so
   this is the reader's first sight of it - and the two wizard steps after it, the editor
   and the ready screen, already wait this way. A line of muted text here made the first
   of the three the odd one out. */
const preparationLoading = (
  <div className="flex flex-col gap-4">
    <LiveRegion>טוען את פרטי המועמדות…</LiveRegion>
    <Skeleton className="block h-20 w-full" />
    <Skeleton className="block h-5 w-2/3" />
    <Skeleton className="block h-5 w-1/2" />
  </div>
);

/* The wait before this screen holds an Operation to report: the projection not yet
   resolved on the redirect from creation. Its heading is the one the record that replaces
   it will carry, from the same table, so the overlay keeps its title through the swap. */
const analysisPending: PendingWork = {
  heading: <>הרצת {operationTypeLabels.analyze_job}</>,
  note: "יוצרים את המועמדות ומנתחים את המשרה…",
};

/* One step of the workflow wizard for one Application: preparing its CV.

   Not a record you browse. The screen used to be a hub of tabs - decisions, facts and the
   diagnosis under one tab bar, the posting and the files under another, a two-axis state
   panel and a recruitment column above them all - several readings of one projection side
   by side. A wizard shows the step, not the record: the progress spine says where the work
   stands across analysis, draft and ready; `PreparationView` is the one action the step is
   waiting on, beside the diagnosis behind it; and the posting and the files sit below as
   reference a press away, never as panels competing for the same space.

   Recruitment is not here at all. Where the application stands with the employer moves on
   its own axis and is managed from the board; putting it beside the CV work claimed a
   relationship between the two that does not exist and crowded the one task this screen is
   for. */
export const ApplicationPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const location = useLocation();

  const query = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = query.data;
  const {
    awaitingRecord,
    operation: watched,
    operationId: watchedId,
    settled,
    watch,
  } = useWatchedOperation(applicationId, detail);

  const { continuation } = useAutomaticDraft({
    applicationId,
    detail,
    operation: watched,
    operationId: watchedId,
    watch,
  });

  const createdApplication = (location.state as { createdApplication?: CreatedApplicationState } | null)
    ?.createdApplication;
  const createdOperationId = createdApplication?.operationId ?? null;

  /* Layout, not passive: it settles before the browser paints, so a creation redirect
     that already knows its Operation id never paints the placeholder card first. Without
     it the watch would open a tick late - after `useWatchedOperation`'s own effect ran -
     and the reader would see the pending wait flash before the record took over, for a
     record already sitting in cache. */
  useLayoutEffect(() => {
    if (createdOperationId !== null) watch(createdOperationId);
  }, [createdOperationId, watch]);

  const viewState = analysisViewState({
    analysisWasQueuedOnCreate: createdOperationId !== null,
    detail,
    operation: watched,
  });
  const pending = watched === undefined && viewState === "processing" ? analysisPending : undefined;
  /* A failed analysis opens the posting for repair, because a malformed posting is one
     cause the reader can fix there. A refusal with no usable provider is not one of
     them: the fix is in Settings, and an open posting with an edit action pointed the
     reader at the wrong place. */
  const { settings } = useSettings();
  const postingRepairRelevant =
    viewState === "analysis_failed" &&
    !(watched?.failure_code === "PROVIDER_REFUSED" && settings !== undefined && !aiRegenerationAvailable(settings));
  const operationLive = isOperationLive({
    awaitingRecord,
    continuation,
    operation: watched,
    pending: pending !== undefined,
    settled,
  });

  /* The files exist only after a revision is rendered, so their reference section is drawn
     only once there is something in it - never as an empty disclosure the reader opens onto
     nothing. */
  const hasArtifacts = detail !== undefined && detail.latest_ready_revision_id != null;

  return (
    /* The analysis step of the wizard. Its name and its spine are the shell's; what is left
       here is the one thing this step is identified by - who the CV is for. The heading
       used to be the target role, which named the record rather than the step and left the
       reader's position stated only by the rail.

       Wide, like the draft and ready steps after it: `PreparationView` puts the facts
       checklist and the matching form beside the full diagnosis, the same two-column shape
       those later steps put the document beside its evidence in. `wideRow`: that split
       reads in the shell's `WideRow` slot rather than inset beside the rail - see that
       component's doc for why beside the rail wasn't safe once the split wanted the
       width the rail's reserved column leaves unused past its own height. */
    <WizardStepShell
      applicationId={applicationId}
      detail={detail}
      measure="wide"
      queryError={query.error}
      /* Only once there is an analysis to lay out across it. Before that the wide row
         holds nothing but the reference material and the bar, and parking them below the
         rail left a hole the rail's height under a one-banner step. */
      wideRow={detail?.latest_analysis != null}
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
      {/* Live work is reported the moment this screen knows about it, whether that
          knowledge came from the projection or - on the redirect straight from creation -
          from the Operation id handed over in route state and seeded into cache before the
          navigate. Placed above `QueryState` on purpose: the projection fetch it gates is a
          second, independent read, and work already known must not wait on it. One
          overlay for the whole stretch: the creation wait, the analysis, and the draft the
          screen continues into are one wait for the reader. */}
      <OperationOverlay
        awaitingRecord={awaitingRecord}
        continuation={continuation}
        onQueued={watch}
        operation={watched}
        pending={pending}
        settled={settled}
      />

      <QueryState
        error={query.error}
        fallbackTitle="לא ניתן לטעון את פרטי המועמדות"
        loading={detail === undefined}
        loadingState={preparationLoading}
      >
        {detail === undefined ? null : detail.application.deleted_at ? (
          /* A deleted Application stays reachable by ID (product-spec.md invariant #20) so
             its history is never orphaned, but this screen is the one place a stale link
             or bookmark could otherwise let someone keep running the preparation workflow
             - generate a draft, approve, submit - against a record the board no longer
             lists. The block is unconditional and replaces the step entirely rather than
             merely warning above it. */
          <Callout role="alert" title="המועמדות הזו נמחקה" tone="warning">
            המועמדות הוסרה מלוח המועמדויות ואין לבצע עליה פעולות הכנה נוספות. תצלום המשרה, הניתוח, הטיוטות, הגרסאות
            שאושרו וכל קובץ שהופק נשארים בדיוק כפי שהם.
          </Callout>
        ) : (
          <div className="space-y-6">
            {/* A successfully queued analysis is reported by the Operation overlay above,
                which follows the run through its current and terminal states. Route state
                only owns the exceptional creation outcome where no Operation exists to
                report; keeping its success message would freeze "running" beside the
                Operation's later "completed" state. */}
            {createdApplication === undefined ||
            createdApplication.analysisSkipped === true ||
            createdOperationId !== null ||
            detail.preparation_state !== "needs_analysis" ||
            watched !== undefined ? null : (
              <Callout role="alert" title="המועמדות נוצרה, אך הניתוח לא הופעל" tone="warning">
                {createdApplication.analysisProblem?.detail ?? "ניתן להפעיל את הניתוח מהמסך הזה."} המועמדות שכבר נוצרה
                לא תיווצר שוב.
              </Callout>
            )}

            {/* A failed run is not the live-work exclusion above: it is history, and the
                projection's own `available_actions`/`recommended_action` do not collapse
                just because the last run failed - "analyze" is still there, and still
                means a fresh run against current Settings, not a repeat of the failed
                one's provider. Withholding this step's action panel here left the retry
                inside the Operation overlay as the only way forward, which can only ever
                repeat the same provider/model that just failed - even after Settings is
                switched to deterministic. */}
            {viewState === "content" || viewState === "analysis_failed" ? (
              <PreparationView detail={detail} onQueued={watch} operationLive={operationLive} />
            ) : null}

            {/* The posting the CV is tailored to, and the files the work produced: reference
                the reader checks or downloads, folded away so the step above stays the
                screen's subject.

                Behind a rule and a quiet heading, because a drawer sitting in the same
                column at the same weight as the step reads as another panel of it - which
                is how a step turns back into a record with sections. The line says where
                the step ends and the material about it begins. */}
            {/* A failed analysis can be repaired only from its source context. In
                particular, updating a malformed posting lives in JobSnapshotPanel, so
                hiding reference material on failure also hid the way out. */}
            {/* Wrapped in `WideRow` so it lands after `PreparationView`'s own wide row
                rather than before it: both portal into the same `afterBody` slot, and
                that slot sits after the whole inset column regardless of source order,
                so this block has to join it too to keep reading last, the way its own
                comment above says it should. */}
            {viewState === "content" || viewState === "analysis_failed" ? (
              <WideRow>
                <div className="flex flex-col gap-2 border-t border-cv-border pt-5">
                  <p className="text-support font-semibold text-cv-text-muted">חומר עזר</p>

                  {postingRepairRelevant ? (
                    /* Repair is the task now, not optional reference reading. Keep the
                       posting and its edit action in view instead of nesting them behind a
                       second disclosure the reader has no reason to discover. */
                    <JobSnapshotPanel detail={detail} operationLive={operationLive} />
                  ) : (
                    <Disclosure summary="צפייה בנוסח המשרה שנשמר">
                      <div className="pt-2">
                        <JobSnapshotPanel detail={detail} operationLive={operationLive} />
                      </div>
                    </Disclosure>
                  )}

                  {hasArtifacts ? (
                    <Disclosure summary="קבצים ותוצרים">
                      <div className="pt-2">
                        <ApplicationArtifacts applicationId={applicationId} />
                      </div>
                    </Disclosure>
                  ) : null}
                </div>
              </WideRow>
            ) : null}
          </div>
        )}
      </QueryState>
    </WizardStepShell>
  );
};
