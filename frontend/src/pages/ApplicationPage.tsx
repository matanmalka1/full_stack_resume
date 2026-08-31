import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";

import { classificationFromAnalysis } from "../api/analyses";
import {
  applicationDetailQueryKey,
  applicationDetailQueryOptions,
  startDraftGeneration,
} from "../api/applications";
import { operationQueryKey } from "../api/operations";
import { settingsQueryOptions } from "../api/settings";
import type { ApplicationDetail, Reason } from "../api/contracts";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { useWatchedOperation } from "../hooks/useWatchedOperation";
import { buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { StatusBadge } from "../ui/StatusBadge";
import { type AutoDraftSources, autoDraftSources } from "./autoDraft";
import { AnalysisPanel, SupersededAnalysisNote } from "./AnalysisPanel";
import { JobSnapshotPanel } from "./JobSnapshotPanel";
import { ReviewDecisionPanel, resolvedByDecisionForm } from "./ReviewDecisionPanel";
import { ApplicationActions } from "./ApplicationActions";
import { RecruitmentPanel } from "./RecruitmentPanel";
import { ApplicationViews, applicationViewFromParam } from "./ApplicationViews";
import { actionDestination } from "./actionDestinations";
import {
  actionLabel,
  recruitmentStatusIcon,
  recruitmentStatusLabel,
  recruitmentStatusTone,
  preparationStateLabels,
  preparationStateTones,
  reasonTitle,
  warningTitle,
  workingDraftStateLabels,
  workingDraftStateTones,
} from "./applicationLabels";

/* `working_draft_state === "none"` is news only once a draft could exist. At the stages
   below it restates the preparation stage, and the masthead is the worst place for a
   restatement: two badges of equal weight read as two independent facts.

   The conjunction with `none` is what keeps this honest, because the stage alone does not
   settle it. `ready_to_draft` is reached by two paths - no draft at all, and a draft whose
   sources went stale - so it implies nothing about a draft on its own. The stale path
   reports `stale` rather than `none` and keeps its badge; only the empty one is silent. */
const IMPLIES_NO_DRAFT = new Set(["needs_analysis", "needs_review", "ready_to_draft"]);

/* Guards against queueing the same automatic draft twice: the session record survives a
   reload, and the in-flight set covers the gap before it is written. Both are keyed by the
   analyze Operation that triggered the continuation. */
const autoDraftInFlight = new Set<string>();

const autoDraftStorageKey = (operationId: string): string => `stage-e:auto-draft:${operationId}`;

const draftStateIsImplied = (detail: ApplicationDetail): boolean =>
  detail.working_draft_state === "none" && IMPLIES_NO_DRAFT.has(detail.preparation_state);

/* Review reasons and stale reasons carry the same shape, and both are now reported as a
   short title plus the control that resolves them.

   The backend's `message` is no longer rendered. It is a complete explanatory sentence,
   and up to five of them stacked on this screen at once - each with its own heading, its
   own list of resolving actions, and its own collapsed code - was the wall this screen
   opened with. The code maps to a title instead, and the action that clears it is a
   button rather than a sentence naming a button.

   Whether the resolving action has a screen is asked of `actionDestination` rather than
   asserted here, so a reason cannot go on promising a screen that now exists. */
const ReasonCallout = ({
  applicationId,
  fallbackTitle,
  reason,
  resolvedHere = false,
  tone,
}: {
  applicationId: string;
  fallbackTitle: string;
  reason: Reason;
  /* The control that resolves this reason is on this screen, so the callout states the
     requirement and offers no destination. */
  resolvedHere?: boolean;
  tone: "blocker" | "warning";
}) => {
  const resolution = resolvedHere
    ? undefined
    : reason.allowed_resolution_actions
        .map((action) => ({ action, href: actionDestination(action, applicationId) }))
        .find((candidate) => candidate.href !== null);

  return (
    <Callout
      action={
        resolution?.href == null ? undefined : (
          <Link className={buttonClasses("secondary")} to={resolution.href}>
            {actionLabel(resolution.action)}
          </Link>
        )
      }
      title={reasonTitle(reason.code, fallbackTitle)}
      tone={tone}
    />
  );
};

/* A.1: the fixed context screen for one Application. It is not a redirect that routes by
   stage - an existing Application can be anywhere in its lifecycle, and choosing a
   destination for it here would be the second workflow state machine the information
   architecture forbids. It renders the §9 projection and offers the actions the
   projection reports. */
export const ApplicationPage = () => {
  const { applicationId } = useParams();
  const location = useLocation();

  /* The route is applications/:applicationId, so a missing id is a router invariant
     violation rather than a state this screen supports. */
  if (applicationId === undefined) {
    throw new Error("ApplicationPage rendered without an applicationId route parameter");
  }

  const queryClient = useQueryClient();
  const automaticAnalysisStartFailed =
    (location.state as { automaticAnalysisStartFailed?: unknown } | null)
      ?.automaticAnalysisStartFailed === true;
  const [searchParams, setSearchParams] = useSearchParams();
  const view = applicationViewFromParam(searchParams.get("view"));
  const query = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = query.data;
  const {
    operation: watched,
    operationId: watchedId,
    panel: operationPanel,
    watch,
  } = useWatchedOperation(applicationId, detail);
  /* The same narrow read the review screen uses, and the same guard: it answers `null`
     unless the analysis on record is the active one, so a superseded analysis is named
     as superseded rather than shown as the classification in force. */
  const classification = detail === undefined ? null : classificationFromAnalysis(detail);
  const supersededAnalysis =
    detail !== undefined && classification === null && detail.latest_analysis != null;
  /* The Web automation opt-in: when Settings ask for it and the analysis raised no review
     reason, the draft follows without a second press. It moved here with the flow. It used
     to live on the Operation screen because that was where a succeeded analyze was seen;
     now that queueing no longer navigates, that screen is not on the path, and leaving the
     chain there would have silently ended the automation.

     The guard itself is unchanged and still `autoDraftSources`: every workflow fact in it
     is the server's, and the dispatch record stays keyed by the analyze Operation so a
     reload cannot queue a second draft for work already continued. */
  const settingsQuery = useQuery(settingsQueryOptions);
  const autoDraft = useMutation({
    mutationFn: async ({ analysisId, applicationId: id, planId }: AutoDraftSources) =>
      startDraftGeneration(id, analysisId, planId, `auto-draft:${watchedId}:${analysisId}:${planId}`),
    onSuccess: ({ operation }) => {
      if (watchedId !== null) {
        sessionStorage.setItem(autoDraftStorageKey(watchedId), "accepted");
        autoDraftInFlight.delete(watchedId);
      }
      queryClient.setQueryData(operationQueryKey(operation.id), operation);
      watch(operation.id);
      void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
    },
    onError: () => {
      if (watchedId !== null) autoDraftInFlight.delete(watchedId);
    },
  });

  useEffect(() => {
    if (watchedId === null) return;
    const sources = autoDraftSources(
      watched,
      settingsQuery.data?.settings,
      detail,
      sessionStorage.getItem(autoDraftStorageKey(watchedId)) === "accepted",
      autoDraftInFlight.has(watchedId),
    );
    if (sources === null) return;
    autoDraftInFlight.add(watchedId);
    autoDraft.mutate(sources);
  }, [detail, settingsQuery.data, watched, watchedId]);

  /* The landmark follows the projection, and says nothing at all until it arrives.

     The recruitment view answers `none` instead: it is not on the workflow path, and
     publishing the preparation stage from it would put the CV's position under a panel
     about the recruiter. That was TrackingPage's own answer before the two views became
     one screen, and it stays attached to the view rather than to the route. */
  useWorkflowStage(
    view === "tracking" ? "none" : detail === undefined ? "unknown" : detail.preparation_state,
  );

  /* The persistent shell already names the company and role. This masthead names
     the view and reports the axis that view is about - never both at once: the two
     are independent, and a card showing them together made every visit start by
     working out which of the two states in front of the reader it was reporting
     (product-spec §399). */
  return (
    <PageShell
      actions={
        detail === undefined ? null : view === "tracking" ? (
          <StatusBadge
            icon={recruitmentStatusIcon(detail.recruitment_status)}
            tone={recruitmentStatusTone(detail.recruitment_status)}
          >
            {recruitmentStatusLabel(detail.recruitment_status)}
          </StatusBadge>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone={preparationStateTones[detail.preparation_state]}>
              {preparationStateLabels[detail.preparation_state]}
            </StatusBadge>
            {/* The draft axis is reported only where it says something the preparation
                stage does not. Before the analysis exists a draft cannot, so "there is no
                active draft" beside "waiting for the job analysis" is one fact wearing
                two badges - and it costs a badge in the masthead, which is where the
                screen's two states are supposed to be distinguishable at a glance. */}
            {draftStateIsImplied(detail) ? null : (
              <StatusBadge tone={workingDraftStateTones[detail.working_draft_state]}>
                {workingDraftStateLabels[detail.working_draft_state]}
              </StatusBadge>
            )}
          </div>
        )
      }
      title={view === "tracking" ? "מעקב גיוס" : "הכנת קורות החיים"}
    >
      <ApplicationViews
        current={view}
        /* `replace` so switching axis does not stack history entries: the two views are
           one place, and "back" must still mean the list. */
        onChange={(next) =>
          setSearchParams(next === "preparation" ? {} : { view: next }, { replace: true })
        }
      />

      <QueryState
        error={query.error}
        fallbackTitle="לא ניתן לטעון את המועמדות"
        loading={detail === undefined}
        loadingLabel="טוען…"
      >
        {detail === undefined ? null : view === "tracking" ? (
          <div
            aria-labelledby="application-view-tab-tracking"
            id="application-view-tracking"
            role="tabpanel"
          >
            <RecruitmentPanel detail={detail} />
          </div>
        ) : (
          <div
            aria-labelledby="application-view-tab-preparation"
            className="flex flex-col gap-5"
            id="application-view-preparation"
            role="tabpanel"
          >
            {automaticAnalysisStartFailed &&
            detail.preparation_state === "needs_analysis" &&
            detail.active_operation == null ? (
              <Callout title="המועמדות נוצרה, אך הניתוח לא הופעל" tone="warning">
                ניתן להפעיל את ניתוח המשרה מהפעולה שלמטה. יצירת המועמדות לא תבוצע שוב.
              </Callout>
            ) : null}

            {/* The work itself, not a link to it. */}
            {operationPanel}

          {/* A review reason whose control is the panel below states the requirement and
              stops there: offering a link beside a form that resolves it on this very
              screen would send the reader away from the answer. Anything the panel does
              not resolve keeps its callout and its resolving action. */}
          {detail.review_reasons.map((reason) => (
            <ReasonCallout
              applicationId={detail.application.id}
              key={reason.code}
              reason={reason}
              fallbackTitle="נדרשת החלטה לפני המשך"
              resolvedHere={resolvedByDecisionForm(reason)}
              tone="blocker"
            />
          ))}

          {detail.stale_reasons.map((reason) => (
            <ReasonCallout
              applicationId={detail.application.id}
              key={reason.code}
              fallbackTitle="הטיוטה אינה מעודכנת מול המקורות שלה"
              reason={reason}
              tone="warning"
            />
          ))}

          {detail.warnings.map((warning) => (
            <Callout key={warning.code} title={warningTitle(warning.code)} tone="warning" />
          ))}

          {detail.newer_draft_in_progress ? (
            <Callout title="קיימת טיוטה חדשה יותר מהגרסה שאושרה" tone="warning">
              הגרסה שאושרה נשמרת בדיוק כפי שהיא. הטיוטה החדשה היא עבודה נפרדת ואינה משנה
              אותה.
            </Callout>
          ) : null}

          {/* The posting the analysis was run against, above the analysis itself: input
              before conclusion. Without it the screen asserted a fit and a confidence
              about a document the reader could not see, and named it only by UUID in the
              provenance block. It is rendered beside the analysis and under the same
              condition, since on its own it is not what this screen is for. */}
          {classification === null ? null : <JobSnapshotPanel detail={detail} />}

          {/* What the analysis concluded, above the control that acts on it. It is the
              reasoning behind the stage the masthead reports, so it belongs on this
              screen rather than on a route the reader would have to leave for. */}
          {classification === null ? null : (
            <AnalysisPanel classification={classification} detail={detail} />
          )}

          {supersededAnalysis ? <SupersededAnalysisNote /> : null}

          {/* The decision itself, directly under the analysis it is about. It was a route
              of its own until the analysis reached this screen; keeping it there would
              have meant deciding on one screen about something shown on another. */}
          <ReviewDecisionPanel detail={detail} />


            <ApplicationActions detail={detail} onQueued={watch} />

          </div>
        )}
      </QueryState>
    </PageShell>
  );
};
