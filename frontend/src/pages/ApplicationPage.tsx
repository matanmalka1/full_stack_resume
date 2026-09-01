import { useQuery } from "@tanstack/react-query";
import { useLocation, useParams, useSearchParams } from "react-router-dom";

import { classificationFromAnalysis } from "../api/analyses";
import { applicationDetailQueryOptions } from "../api/applications";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { useWatchedOperation } from "../hooks/useWatchedOperation";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { StatusBadge } from "../ui/StatusBadge";
import { ViewSwitch } from "../ui/ViewSwitch";
import { applicationViewFromParam, applicationViews } from "./ApplicationViews";
import { PreparationView } from "./application/PreparationView";
import { TrackingView } from "./application/TrackingView";
import {
  draftStateIsImplied,
  recruitmentStatusIcon,
  recruitmentStatusLabel,
  recruitmentStatusTone,
  preparationStateLabels,
  preparationStateTones,
  workingDraftStateLabels,
  workingDraftStateTones,
} from "./application/applicationLabels";
import { useAutomaticDraft } from "./application/useAutomaticDraft";

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

  const automaticAnalysisStartFailed =
    (location.state as { automaticAnalysisStartFailed?: unknown } | null)?.automaticAnalysisStartFailed === true;
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
  const supersededAnalysis = detail !== undefined && classification === null && detail.latest_analysis != null;
  /* The Web automation opt-in follows the watched analyze Operation. Its side effects
     live in the hook that owns dispatch and deduplication rather than in this page shell. */
  useAutomaticDraft({
    applicationId,
    detail,
    operation: watched,
    operationId: watchedId,
    watch,
  });

  /* The landmark follows the projection, and says nothing at all until it arrives.

     The recruitment view answers `none` instead: it is not on the workflow path, and
     publishing the preparation stage from it would put the CV's position under a panel
     about the recruiter. That was TrackingPage's own answer before the two views became
     one screen, and it stays attached to the view rather than to the route. */
  useWorkflowStage(view === "tracking" ? "none" : detail === undefined ? "unknown" : detail.preparation_state);

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
      <ViewSwitch
        label="תצוגות המועמדות"
        /* `replace` so switching axis does not stack history entries: the two views are
           one place, and "back" must still mean the list. */
        onChange={(next) => setSearchParams(next === "preparation" ? {} : { view: next }, { replace: true })}
        options={[...applicationViews]}
        value={view}
      />

      <QueryState
        error={query.error}
        fallbackTitle="לא ניתן לטעון את המועמדות"
        loading={detail === undefined}
        loadingLabel="טוען…"
      >
        {detail === undefined ? null : view === "tracking" ? (
          <TrackingView detail={detail} />
        ) : (
          <PreparationView
            automaticAnalysisStartFailed={automaticAnalysisStartFailed}
            classification={classification}
            detail={detail}
            onQueued={watch}
            operationPanel={operationPanel}
            supersededAnalysis={supersededAnalysis}
          />
        )}
      </QueryState>
    </PageShell>
  );
};
