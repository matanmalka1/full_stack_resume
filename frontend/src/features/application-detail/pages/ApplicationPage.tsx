import { useQuery } from "@tanstack/react-query";
import { useLayoutEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { watchedApplicationDetailQueryOptions } from "@/api/applications";
import type { ProblemDetails } from "@/api/client";
import type { RecruitmentStatus } from "@/api/contracts";
import { routePaths } from "@/navigation/routePaths";
import { useRequiredParam } from "@/navigation/useRequiredParam";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Disclosure } from "@/ui/Disclosure";
import { problemSentence } from "@/ui/errorMessages";
import { QueryState } from "@/ui/QueryState";
import { WideRow } from "@/ui/WideRow";
import { formatDateTime } from "@/utils/formatDateTime";
import { LiveRegion } from "@/ui/LiveRegion";
import { Skeleton } from "@/ui/Skeleton";
import { SuccessNotice } from "@/ui/SuccessNotice";
import {
  OperationOverlay,
  type PendingWork,
  isOperationLive,
  operationTypeLabels,
  useWatchedOperation,
} from "@/features/operations";
import { PreparationChecklist, PreparationView, WizardStepShell, useAutomaticDraft } from "@/features/preparation";
import {
  ApplicationDetailsDialog,
  ApplicationRecordActions,
  CloseApplicationDialog,
  DeleteApplicationDialog,
  useApplicationListMutations,
} from "@/features/application-list";
import { RecruitmentUpdateDialog } from "@/features/recruitment";
import { applicationLabel } from "../model/applicationPresentation";
import { analysisViewState } from "../model/analysisViewState";
import { listItemFromDetail } from "../model/applicationListItem";
import { ApplicationFacts } from "../components/ApplicationFacts";
import { JobPostingPanel } from "../components/JobPostingPanel";
import { NextActionCard } from "../components/NextActionCard";
import { RecruitmentStageCard } from "../components/RecruitmentStageCard";

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

   Recruitment is stated, not managed, here. Where the application stands with the
   employer moves on its own axis; it was once left off this screen entirely, so as not
   to claim a relationship with the CV work that does not exist. The mobile design brought
   it back as the opening card, because a reader who opens an application asks where it
   stands before what to do with its CV. It sits above the step, on its own card with its
   own reminder beside it, and changing it opens the board's recruitment manager rather
   than growing a second editor here. */
export const ApplicationPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const location = useLocation();

  const query = useQuery(watchedApplicationDetailQueryOptions(applicationId));
  const [managingRecruitment, setManagingRecruitment] = useState(false);
  /* Which of the board's record commands is open over this screen. */
  const [recordDialog, setRecordDialog] = useState<"close" | "delete" | "details" | null>(null);
  /* A close just made, kept so it can be undone - the board's own offer, made here too. */
  const [closed, setClosed] = useState<{ eventId: string | null; previousStatus: RecruitmentStatus } | null>(null);
  const detail = query.data;
  /* The board's command mutations, so a close or a delete here is the same command the
     board issues and invalidates the same views. A deleted record is not navigated away
     from: the projection re-read marks it deleted, and this screen's deletion notice
     takes the step's place. */
  const { clearNextActionMutation, closeMutation, deleteMutation, undoCloseMutation } = useApplicationListMutations({
    onApplicationClosed: (_applicationId, eventId) => {
      setRecordDialog(null);
      if (detail !== undefined) {
        setClosed({ eventId: eventId ?? null, previousStatus: detail.recruitment_status as RecruitmentStatus });
      }
    },
    onApplicationDeleted: () => setRecordDialog(null),
    onCloseUndone: () => setClosed(null),
    onNextActionCleared: () => undefined,
  });
  const record = detail === undefined ? null : listItemFromDetail(detail);
  const { awaitingRecord, operation: watched, settled, watch } = useWatchedOperation(applicationId, detail);

  const { continuation } = useAutomaticDraft({
    applicationId,
    detail,
    operation: watched,
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
     cause the reader can fix there. A run with no provider configured is not one of
     them: the fix is in Settings, and an open posting with an edit action pointed the
     reader at the wrong place. */
  const postingRepairRelevant = viewState === "analysis_failed" && watched?.failure_code !== "PROVIDER_NOT_CONFIGURED";
  const operationLive = isOperationLive({
    awaitingRecord,
    continuation,
    operation: watched,
    pending: pending !== undefined,
    settled,
  });

  /* The masthead's commands on a wide screen, the design's top end: the recruitment
     manager, and the way on to the screen the CV work continues on once there is one.
     Both are wide-only - a phone opens the manager from the stage card and reaches the
     editor from the checklist's row - so neither name is on the page twice. While the run
     is the step's whole body, or the record is gone, the masthead offers nothing: the run
     card and the deletion notice are the answer then. */
  const continueTo =
    detail === undefined || detail.document_id == null
      ? null
      : detail.preparation_state === "ready"
        ? { label: "לקורות החיים המוכנים", to: routePaths.ready(applicationId) }
        : detail.preparation_state === "draft_in_progress" || detail.preparation_state === "approved"
          ? { label: "המשך לעריכת הטיוטה", to: routePaths.draft(applicationId) }
          : null;
  const headerActions =
    detail === undefined || detail.application.deleted_at != null || viewState === "processing" ? undefined : (
      <div className="flex items-center gap-2 max-lg:hidden">
        <Button onClick={() => setManagingRecruitment(true)} variant="secondary">
          עדכון סטטוס
        </Button>
        {/* The board's record menu (screen 24): the recruitment manager again, the
            record's details, and the two commands that end it. */}
        {record === null ? null : (
          <ApplicationRecordActions
            item={record}
            onRequestClose={() => setRecordDialog("close")}
            onRequestDelete={() => setRecordDialog("delete")}
            onRequestDetails={() => setRecordDialog("details")}
            onRequestUpdate={() => setManagingRecruitment(true)}
            variant="record"
          />
        )}
        {continueTo === null ? null : (
          <Link className={buttonClasses("primary")} to={continueTo.to}>
            {continueTo.label}
          </Link>
        )}
      </div>
    );

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
      /* A phone's header names the application itself - its initial, the role, and the
         company with the day it was taken in - since the stage card and the checklist
         below say where the work stands, so its stage bar is left out. */
      phoneHeader={{
        bar: false,
        mark: true,
        ...(detail === undefined
          ? {}
          : {
              subtitle: (
                <span dir="auto">
                  {detail.application.company} · נקלטה ב־{formatDateTime(detail.application.created_at, "date")}
                </span>
              ),
            }),
      }}
      /* A wide screen heads the step as the record it is for, as its design does: the
         company's initial, the role as the title over "company · taken in on", the trail
         back to the board, and the commands at the row's end. The stepper stays under it
         once there is an analysis to lay out (screen 16); before that the checklist in the
         body says where the work stands, and the spine would say it twice.

         The role is the title from the large breakpoint only (the shell's rule): a
         phone's compact header already names it, and keeps the stage's name as the
         heading's accessible name. */
      desktopHeader={{
        actions: headerActions,
        breadcrumb: true,
        mark: true,
        spine: detail?.latest_analysis != null,
        ...(detail === undefined
          ? {}
          : {
              subtitle: (
                <span dir="auto">
                  {detail.application.company} · נקלטה ב־{formatDateTime(detail.application.created_at, "date")}
                </span>
              ),
              title: <span dir="auto">{detail.application.target_role}</span>,
            }),
      }}
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
        eyebrow={detail === undefined ? undefined : `${detail.application.target_role} · ${detail.application.company}`}
        /* While the analysis runs this step has no body to show - `PreparationView` waits
           for its result - so the run is reported where that body will be, not in a corner
           over an empty page. */
        inline={viewState === "processing"}
        onQueued={watch}
        operation={watched}
        pending={pending}
        /* While the analysis runs this step has no bar of its own - `PreparationView`
           waits for the result - so the run closes on its own ways on. */
        runActions={viewState === "processing"}
        settled={settled}
      />

      <QueryState
        error={query.error}
        errorTitle="לא ניתן לטעון את פרטי המועמדות"
        loading={detail === undefined}
        loadingState={preparationLoading}
        onRetry={() => void query.refetch()}
      >
        {detail === undefined ? null : detail.application.deleted_at ? (
          /* A deleted Application stays reachable by ID (product-spec.md invariant #20) so
             its history is never orphaned, but this screen is the one place a stale link
             or bookmark could otherwise let someone keep running the preparation workflow
             - generate a draft, approve, submit - against a record the board no longer
             lists. The block is unconditional and replaces the step entirely rather than
             merely warning above it. */
          <Callout role="alert" title="המועמדות הזו נמחקה" tone="warning">
            המועמדות הוסרה מלוח המועמדויות ואין לבצע עליה פעולות הכנה נוספות. נוסח המשרה, הניתוח, מסמך קורות החיים
            וההגשות שנרשמו נשארים בדיוק כפי שהם.
          </Callout>
        ) : (
          <div className="space-y-6">
            {/* The close just made, where the eye is, with the board's own way back. */}
            {closed === null ? null : (
              <SuccessNotice onDismiss={() => setClosed(null)} title="המועמדות נסגרה והועברה למועמדויות הסגורות">
                {closed.eventId === null ? null : (
                  <Button
                    onClick={() =>
                      undoCloseMutation.mutate({
                        applicationId,
                        eventId: closed.eventId ?? "",
                        previousStatus: closed.previousStatus,
                      })
                    }
                    pending={undoCloseMutation.isPending}
                    pendingLabel="מבטל סגירה…"
                    size="compact"
                    variant="secondary"
                  >
                    ביטול הסגירה
                  </Button>
                )}
              </SuccessNotice>
            )}
            {/* Where the application stands with the employer, and the reminder the reader
                set for it - the two things a reader opening it from the board asks before
                the CV work. Both open the board's own recruitment manager to change them.
                Withheld while a run is the step's whole body: then the run is the answer. */}
            {/* Then where the CV work stands, as the checklist of its five steps.

                One grid at every width, so a phone keeps its single column in this order
                - stage, reminder, checklist - while a wide screen places the same three
                as the design's two columns: the stage and the checklist in the main one,
                and an aside at the end side holding the reminder over the record at a
                glance (`ApplicationFacts`, wide only). The aside is `contents` on a phone,
                so it adds no row of its own when there is no reminder. */}
            {viewState === "processing" ? null : (
              <div className="grid items-start gap-3 lg:grid-cols-[minmax(0,1fr)_20rem] lg:grid-rows-[auto_1fr] lg:gap-x-6 lg:gap-y-5">
                <div className="min-w-0 lg:col-start-1 lg:row-start-1">
                  <RecruitmentStageCard detail={detail} onUpdate={() => setManagingRecruitment(true)} />
                </div>
                <div className="flex min-w-0 flex-col gap-3 max-lg:contents lg:col-start-2 lg:row-span-2 lg:row-start-1">
                  <NextActionCard detail={detail} onUpdate={() => setManagingRecruitment(true)} />
                  <ApplicationFacts detail={detail} />
                </div>
                <div className="min-w-0 max-lg:mt-3 lg:col-start-1 lg:row-start-2">
                  <PreparationChecklist detail={detail} />
                </div>
              </div>
            )}

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
                {problemSentence({ problem: createdApplication.analysisProblem }, "אפשר להפעיל את הניתוח מהמסך הזה.")}
              </Callout>
            )}

            {/* A failed run is not the live-work exclusion above: it is history, and the
                projection's own `available_actions`/`recommended_action` do not collapse
                just because the last run failed - "analyze" is still there, and still
                means a fresh run against current Settings, not a repeat of the failed
                one's provider. Withholding this step's action panel here left the retry
                inside the Operation overlay as the only way forward, which can only ever
                repeat the same provider/model that just failed. */}
            {viewState === "content" || viewState === "analysis_failed" ? (
              <PreparationView detail={detail} onQueued={watch} operationLive={operationLive} />
            ) : null}

            {/* The posting the CV is tailored to: reference the reader checks or repairs,
                folded away so the step above stays the screen's subject.

                Behind a rule and a quiet heading, because a drawer sitting in the same
                column at the same weight as the step reads as another panel of it - which
                is how a step turns back into a record with sections. The line says where
                the step ends and the material about it begins. */}
            {/* A failed analysis can be repaired only from its source context. In
                particular, updating a malformed posting lives in JobPostingPanel, so
                hiding reference material on failure also hid the way out. */}
            {/* Wrapped in `WideRow` so it lands after `PreparationView`'s own wide row
                rather than before it: both portal into the same `afterBody` slot, and
                that slot sits after the whole inset column regardless of source order,
                so this block has to join it too to keep reading last, the way its own
                comment above says it should. */}
            {viewState === "content" || viewState === "analysis_failed" ? (
              <WideRow>
                {/* On a phone the rule and the quiet heading give way to a card row of its
                    own, the shape every folded section on a phone's screen takes, so the
                    posting reads as one tap away rather than as a footnote under the step. */}
                <div className="flex flex-col gap-2 border-t border-cv-border pt-5 max-lg:border-t-0 max-lg:pt-0">
                  <p className="text-support font-semibold text-cv-text-muted max-lg:sr-only">חומר עזר</p>

                  {postingRepairRelevant ? (
                    /* Repair is the task now, not optional reference reading. Keep the
                       posting and its edit action in view instead of nesting them behind a
                       second disclosure the reader has no reason to discover. */
                    <JobPostingPanel detail={detail} operationLive={operationLive} />
                  ) : (
                    <Disclosure flush summary="צפייה בנוסח המשרה שנשמר" variant="card">
                      <div className="pt-2">
                        <JobPostingPanel detail={detail} operationLive={operationLive} />
                      </div>
                    </Disclosure>
                  )}
                </div>
              </WideRow>
            ) : null}
          </div>
        )}
      </QueryState>

      <CloseApplicationDialog
        application={recordDialog === "close" ? record : null}
        onCancel={() => setRecordDialog(null)}
        onConfirm={() => closeMutation.mutate(applicationId)}
        pending={closeMutation.isPending}
      />
      <DeleteApplicationDialog
        application={recordDialog === "delete" ? record : null}
        onCancel={() => setRecordDialog(null)}
        onConfirm={() => deleteMutation.mutate(applicationId)}
        pending={deleteMutation.isPending}
      />
      <ApplicationDetailsDialog
        application={recordDialog === "details" ? record : null}
        clearing={clearNextActionMutation.isPending}
        onClearNextAction={() => clearNextActionMutation.mutate(applicationId)}
        onClose={() => setRecordDialog(null)}
        onRequestUpdate={() => {
          setRecordDialog(null);
          setManagingRecruitment(true);
        }}
      />
      <RecruitmentUpdateDialog
        application={
          managingRecruitment && detail !== undefined
            ? {
                company: detail.application.company,
                id: detail.application.id,
                target_role: detail.application.target_role,
              }
            : null
        }
        onClose={() => setManagingRecruitment(false)}
      />
    </WizardStepShell>
  );
};
