import { useQuery } from "@tanstack/react-query";
import { useLocation, useParams } from "react-router-dom";

import { classificationFromAnalysis } from "../api/analyses";
import { applicationDetailQueryOptions } from "../api/applications";
import { useWorkflowStage, workflowDestinations } from "../app/WorkflowLandmark";
import { useWatchedOperation } from "../hooks/useWatchedOperation";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { StatusBadge } from "../ui/StatusBadge";
import { ApplicationSectionNav } from "./ApplicationSectionNav";
import { PreparationView } from "./application/PreparationView";
import {
  draftStateIsImplied,
  preparationStateLabels,
  preparationStateTones,
  workingDraftStateLabels,
  workingDraftStateTones,
} from "./application/applicationLabels";
import { useAutomaticDraft } from "./application/useAutomaticDraft";

/* The CV preparation screen for one Application. It renders the §9 projection and offers
   only the document-workflow actions the backend reports. */
export const ApplicationPage = () => {
  const { applicationId } = useParams();
  const location = useLocation();

  /* The route is applications/:applicationId/preparation, so a missing id is a router invariant
     violation rather than a state this screen supports. */
  if (applicationId === undefined) {
    throw new Error("ApplicationPage rendered without an applicationId route parameter");
  }

  const automaticAnalysisStartFailed =
    (location.state as { automaticAnalysisStartFailed?: unknown } | null)?.automaticAnalysisStartFailed === true;
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

  useWorkflowStage(
    detail === undefined ? "unknown" : detail.preparation_state,
    workflowDestinations(applicationId, detail),
  );

  /* The persistent shell already names the company and role. This masthead names
     the view and reports the axis that view is about - never both at once: the two
     are independent, and a card showing them together made every visit start by
     working out which of the two states in front of the reader it was reporting
     (product-spec §399). */
  return (
    <PageShell
      actions={
        detail === undefined ? null : (
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
      navigation={<ApplicationSectionNav applicationId={applicationId} value="preparation" />}
      title="הכנת קורות החיים"
    >
      <QueryState
        error={query.error}
        fallbackTitle="לא ניתן לטעון את המועמדות"
        loading={detail === undefined}
        loadingLabel="טוען…"
      >
        {detail === undefined ? null : (
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
