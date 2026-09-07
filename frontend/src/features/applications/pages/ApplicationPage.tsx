import { useQuery } from "@tanstack/react-query";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { applicationDetailQueryOptions } from "@/api/applications";
import type { ProblemDetails } from "@/api/client";
import { routePaths } from "@/app/routePaths";
import { useRequiredParam } from "@/app/useRequiredParam";
import { useWatchedOperation } from "@/features/operations";
import { Callout } from "@/ui/Callout";
import { PageShell } from "@/ui/PageShell";
import { QueryState } from "@/ui/QueryState";
import { TabPanel } from "@/ui/Tabs";
import { ActiveOperationPanel } from "@/features/operations";
import {
  PreparationView,
  PreparationWorkflowSteps,
  openDecisionCount,
  openDecisions,
  useAutomaticDraft,
} from "@/features/preparation";
import { RecruitmentManagerButton } from "@/features/recruitment";
import { ApplicationArtifacts } from "../components/ApplicationArtifacts";
import { ApplicationBreadcrumbs } from "../components/ApplicationBreadcrumbs";
import { ApplicationPrimaryAction } from "../components/ApplicationPrimaryAction";
import { ApplicationStatePanel } from "../components/ApplicationStatePanel";
import {
  APPLICATION_TAB_GROUP,
  type ApplicationTab,
  ApplicationTabs,
  isApplicationTab,
} from "../components/ApplicationTabs";
import { JobSnapshotPanel } from "../components/JobSnapshotPanel";

/* The news that an Application was just created, handed over in route state by the intake
   screen. It is the one thing on this page that is not read from the projection, because
   it is about the request that made the record rather than about the record. */
interface CreatedApplicationState {
  analysisProblem?: ProblemDetails | null;
  analysisQueued?: unknown;
}

/* One screen for one Application: what it is, where it stands on both axes, and the three
   domains it opens into - preparing its CV, the posting it is for, and the files that
   work produced.

   The screen composes; it executes nothing. Preparation owns its own workflow and its own
   commands, recruitment owns its status and its dialog, and what is left here is the
   Application's identity, the state band that keeps the two axes apart, and the one
   destination the projection says the work is waiting on.

   `/applications/:id/preparation` is a second address for this same screen with the
   preparation tab selected: the document workflow is linked to and bookmarked directly,
   so it keeps a name of its own. The other two tabs are `?tab=`, and selecting one moves
   the URL between the two forms rather than leaving `/preparation?tab=job` standing. */
export const ApplicationPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const tabParam = searchParams.get("tab");
  const currentTab: ApplicationTab = isApplicationTab(tabParam)
    ? tabParam
    : location.pathname.endsWith("/preparation")
      ? "preparation"
      : "job";

  const selectTab = (nextTab: ApplicationTab) =>
    navigate(
      nextTab === "preparation"
        ? routePaths.preparation(applicationId)
        : `${routePaths.application(applicationId)}?tab=${nextTab}`,
      { replace: true },
    );

  const query = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = query.data;
  const { operation: watched, operationId: watchedId, watch } = useWatchedOperation(applicationId, detail);

  useAutomaticDraft({
    applicationId,
    detail,
    operation: watched,
    operationId: watchedId,
    watch,
  });

  const createdApplication = (location.state as { createdApplication?: CreatedApplicationState } | null)
    ?.createdApplication;
  const openDecisionsCount = detail === undefined ? 0 : openDecisionCount(openDecisions(detail));

  return (
    <PageShell
      actions={
        detail === undefined ? null : (
          <div className="flex flex-wrap items-center gap-2">
            <ApplicationPrimaryAction detail={detail} />
            <RecruitmentManagerButton application={detail.application} />
          </div>
        )
      }
      eyebrow={detail === undefined ? undefined : <span dir="auto">{detail.application.company}</span>}
      landmark={<PreparationWorkflowSteps applicationId={applicationId} detail={detail} />}
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
              <Callout role="status" title="המועמדות נוצרה, הניתוח רץ" tone="progress" />
            ) : (
              <Callout role="alert" title="המועמדות נוצרה, אך הניתוח לא הופעל" tone="warning">
                {createdApplication.analysisProblem?.detail ?? "ניתן להפעיל את הניתוח מלשונית הכנת קורות החיים."}{" "}
                המועמדות שכבר נוצרה לא תיווצר שוב.
              </Callout>
            )}

            {/* Live work is the Application's, not one tab's: an analysis queued from the
                preparation tab is still running while the reader is reading the posting.
                It is reported once, above the tabs, rather than once here and again inside
                preparation - which is what put two copies of the panel on screen on the
                first visit after an Application was created. */}
            {watched === undefined ? null : <ActiveOperationPanel onQueued={watch} operation={watched} />}

            <ApplicationStatePanel
              detail={detail}
              onOpenPreparation={() => selectTab("preparation")}
              openDecisionsCount={openDecisionsCount}
            />

            <ApplicationTabs
              active={currentTab}
              detail={detail}
              onSelect={selectTab}
              openDecisionsCount={openDecisionsCount}
            />

            <TabPanel active={currentTab === "preparation"} group={APPLICATION_TAB_GROUP} tab="preparation">
              <PreparationView detail={detail} onQueued={watch} />
            </TabPanel>

            <TabPanel active={currentTab === "job"} group={APPLICATION_TAB_GROUP} tab="job">
              <JobSnapshotPanel detail={detail} />
            </TabPanel>

            <TabPanel active={currentTab === "artifacts"} group={APPLICATION_TAB_GROUP} tab="artifacts">
              <ApplicationArtifacts applicationId={applicationId} />
            </TabPanel>
          </div>
        )}
      </QueryState>
    </PageShell>
  );
};
