import { useQuery } from "@tanstack/react-query";
import { useLocation, useSearchParams } from "react-router-dom";

import { classificationFromAnalysis } from "../api/analyses";
import { applicationDetailQueryOptions } from "../api/applications";
import type { ProblemDetails } from "../api/client";
import { useRequiredParam } from "../app/useRequiredParam";
import { useWorkflowStage, workflowDestinations } from "../app/WorkflowLandmark";
import { useWatchedOperation } from "../hooks/useWatchedOperation";
import { Callout } from "../ui/Callout";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { ActiveOperationPanel } from "./ActiveOperationPanel";
import { ApplicationBreadcrumbs } from "./application/ApplicationBreadcrumbs";
import { ApplicationHubTabs, type ApplicationHubTab, HubTabPanel } from "./application/ApplicationHubTabs";
import { ArtifactsPanel } from "./application/ArtifactsPanel";
import { JobSnapshotPanel } from "./application/JobSnapshotPanel";
import { PreparationStatusBadges } from "./application/PreparationStatusBadges";
import { PreparationView } from "./application/PreparationView";
import { openDecisionCount, openDecisions } from "./application/ReviewDecisionForm";
import { useAutomaticDraft } from "./application/useAutomaticDraft";
import { RecruitmentManagerButton } from "./recruitment/RecruitmentManagerButton";

const isHubTab = (value: string | null): value is ApplicationHubTab =>
  value === "job" || value === "preparation" || value === "artifacts";

/* One screen for the Application: the job record, the CV preparation workflow, and the
   artifacts it has produced, as tabs of one hub rather than two screens joined by a hop
   through a gate card. Recruitment tracking stays one shared dialog reachable from the
   masthead, not a tab - it is a status to update in passing, not a place to read from.
   `/applications/:id/preparation` still resolves - it lands here with the preparation tab
   selected, so existing links and bookmarks keep working. */
export const JobDetailsPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();

  const isPreparationPath = location.pathname.endsWith("/preparation");
  const tabParam = searchParams.get("tab");
  const currentTab: ApplicationHubTab = isHubTab(tabParam) ? tabParam : isPreparationPath ? "preparation" : "job";

  const handleTabChange = (nextTab: ApplicationHubTab) => {
    setSearchParams(
      (prev) => {
        const updated = new URLSearchParams(prev);
        updated.set("tab", nextTab);
        return updated;
      },
      { replace: true },
    );
  };

  const query = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = query.data;
  const { operation: watched, operationId: watchedId, watch } = useWatchedOperation(applicationId, detail);

  const classification = detail === undefined ? null : classificationFromAnalysis(detail);
  const supersededAnalysis = detail !== undefined && classification === null && detail.latest_analysis != null;

  useAutomaticDraft({
    applicationId,
    detail,
    operation: watched,
    operationId: watchedId,
    watch,
  });

  const createdApplication = (
    location.state as {
      createdApplication?: {
        analysisProblem?: ProblemDetails | null;
        analysisQueued?: unknown;
      };
    } | null
  )?.createdApplication;

  useWorkflowStage(
    detail === undefined ? "unknown" : detail.preparation_state,
    workflowDestinations(applicationId, detail),
  );

  const openDecisionsCount = detail === undefined ? 0 : openDecisionCount(openDecisions(detail));

  return (
    <PageShell
      actions={
        detail === undefined ? null : (
          <div className="flex flex-wrap items-center gap-2">
            <PreparationStatusBadges detail={detail} hideStageImpliedStatus />
            <RecruitmentManagerButton application={detail.application} />
          </div>
        )
      }
      eyebrow={detail === undefined ? undefined : <span dir="auto">{detail.application.company}</span>}
      navigation={
        <ApplicationBreadcrumbs
          applicationId={applicationId}
          company={detail?.application.company}
          page={currentTab === "preparation" ? "preparation" : "job"}
          targetRole={detail?.application.target_role}
        />
      }
      title={detail?.application.target_role ?? "פרטי משרה"}
    >
      <QueryState
        error={query.error}
        fallbackTitle="לא ניתן לטעון את פרטי המועמדות"
        loading={detail === undefined}
        loadingLabel="טוען את פרטי המועמדות…"
      >
        {detail === undefined ? null : (
          <div className="space-y-6">
            {createdApplication === undefined ? null : createdApplication.analysisQueued === true ? (
              watched === undefined ? (
                <Callout role="status" title="המועמדות נוצרה, הניתוח רץ" tone="progress" />
              ) : (
                <ActiveOperationPanel onQueued={watch} operation={watched} />
              )
            ) : (
              <Callout role="alert" title="המועמדות נוצרה, אך הניתוח לא הופעל" tone="warning">
                {createdApplication.analysisProblem?.detail ?? "ניתן להפעיל את הניתוח מלשונית הכנת קורות החיים."} המועמדות
                שכבר נוצרה לא תיווצר שוב.
              </Callout>
            )}

            <ApplicationHubTabs
              active={currentTab}
              detail={detail}
              onSelect={handleTabChange}
              openDecisionsCount={openDecisionsCount}
            />

            <HubTabPanel active={currentTab} tab="preparation">
              <PreparationView
                classification={classification}
                detail={detail}
                onQueued={watch}
                operationPanel={
                  watched === undefined ? null : <ActiveOperationPanel onQueued={watch} operation={watched} />
                }
                supersededAnalysis={supersededAnalysis}
              />
            </HubTabPanel>

            <HubTabPanel active={currentTab} tab="job">
              <JobSnapshotPanel detail={detail} />
            </HubTabPanel>

            <HubTabPanel active={currentTab} tab="artifacts">
              <ArtifactsPanel applicationId={applicationId} />
            </HubTabPanel>
          </div>
        )}
      </QueryState>
    </PageShell>
  );
};
