import { useQuery } from "@tanstack/react-query";

import { classificationFromAnalysis } from "../api/analyses";
import { applicationDetailQueryOptions } from "../api/applications";
import { appRoutes } from "../app/appRoutes";
import { useRequiredParam } from "../app/useRequiredParam";
import { useWorkflowStage, workflowDestinations } from "../app/WorkflowLandmark";
import { useWatchedOperation } from "../hooks/useWatchedOperation";
import { BackLink } from "../ui/BackLink";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { ActiveOperationPanel } from "./ActiveOperationPanel";
import { PreparationStatusBadges } from "./application/PreparationStatusBadges";
import { PreparationView } from "./application/PreparationView";
import { useAutomaticDraft } from "./application/useAutomaticDraft";

/* The CV preparation screen for one Application. It renders the §9 projection and offers
   only the document-workflow actions the backend reports. */
export const ApplicationPage = () => {
  const applicationId = useRequiredParam("applicationId");

  const query = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = query.data;
  const {
    operation: watched,
    operationId: watchedId,
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
          <PreparationStatusBadges
            className="flex flex-wrap items-center gap-2"
            detail={detail}
            hideStageImpliedStatus
          />
        )
      }
      /* Up to the job the CV is being written for, not across to a peer tab: preparation
         is entered from Job Detail and returns there. */
      navigation={
        <BackLink label="חזרה לפרטי המשרה" to={appRoutes.application(applicationId)}>
          פרטי משרה
        </BackLink>
      }
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
            classification={classification}
            detail={detail}
            onQueued={watch}
            operationPanel={
              watched === undefined ? null : <ActiveOperationPanel onQueued={watch} operation={watched} />
            }
            supersededAnalysis={supersededAnalysis}
          />
        )}
      </QueryState>
    </PageShell>
  );
};
