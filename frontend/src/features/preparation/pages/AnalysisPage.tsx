import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, SlidersHorizontal } from "lucide-react";
import { useLayoutEffect } from "react";
import { Link, useLocation } from "react-router-dom";

import { classificationFromAnalysis } from "@/api/analyses";
import { watchedApplicationDetailQueryOptions } from "@/api/applications";
import type { ProblemDetails } from "@/api/client";
import { aiAvailability } from "@/api/settings";
import type { ApplicationDetail } from "@/api/contracts";
import {
  OperationOverlay,
  type PendingWork,
  isOperationLive,
  operationTypeLabels,
  useWatchedOperation,
} from "@/features/operations";
import { routePaths } from "@/navigation/routePaths";
import { useIsPhone } from "@/ui/useIsPhone";
import { useRequiredParam } from "@/navigation/useRequiredParam";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { problemSentence } from "@/ui/errorMessages";
import { cardClasses } from "@/ui/surface";
import { useAnalyzeCommand, useAutomaticDraft } from "../api/mutations";
import { StepFrame } from "../components/StepFrame";
import { analysisViewState } from "../model/analysisViewState";
import { matchingValuesFrom } from "../model/matchingConfiguration";
import { workflowDestinations } from "../model/workflowStages";
import { AnalysisOverview } from "../stages/analysis/AnalysisOverview";

/* The news that an Application was just created, handed over in route state by the intake
   screen. It is about the request that made the record rather than about the record, so
   it is the one thing here not read from the projection. */
interface CreatedApplicationState {
  analysisProblem?: ProblemDetails | null;
  /* Intake did not request analysis because no AI provider exists; the step says so
     itself, so the "was not started" warning is not repeated. */
  analysisSkipped?: boolean;
  operationId?: string | null;
}

/* The wait before this screen holds an Operation to report: the projection not yet
   resolved on the redirect from creation. Its heading is the one the record that replaces
   it will carry, so the screen keeps its title through the swap. */
const analysisPending: PendingWork = {
  heading: <>הרצת {operationTypeLabels.analyze_job}</>,
  note: "יוצרים את המועמדות ומנתחים את המשרה…",
};

const loading = (
  <div className="flex flex-col gap-4">
    <LiveRegion>טוען את הניתוח…</LiveRegion>
    <Skeleton className="block h-24 w-full" />
    <Skeleton className="block h-64 w-full" />
  </div>
);

/* The step before any analysis is in force: none was run yet, or the last one read an
   older posting. Its one command is the analysis itself. */
const AnalyzeFirst = ({
  detail,
  onQueued,
  operationLive,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  operationLive: boolean;
}) => {
  const { analyze, settings } = useAnalyzeCommand(detail, onQueued);
  const ai = aiAvailability(settings);
  const superseded = detail.latest_analysis != null;
  const offered = detail.available_actions.includes("analyze");

  return (
    <section aria-labelledby="analyze-first-heading" className={cardClasses("flex flex-col gap-3 p-5")}>
      <h2 className="text-heading-card font-extrabold text-cv-text" id="analyze-first-heading">
        {superseded ? "הניתוח האחרון נעשה מול נוסח קודם" : "המשרה טרם נותחה"}
      </h2>
      <p className="text-label leading-relaxed text-cv-text-muted">
        {superseded
          ? "נוסח המשרה השתנה מאז הניתוח האחרון, ולכן הוא אינו מוצג כאן. ניתוח חדש מול הנוסח הנוכחי יציג את ההתאמה העדכנית."
          : "ניתוח המשרה קובע את ההתאמה, את הפערים ואת העובדות שייכנסו לקורות החיים."}
      </p>
      {analyze.error === null ? null : (
        <ErrorCallout
          error={analyze.error}
          fallbackDetail="מצב המועמדות לא השתנה. אפשר לנסות שוב."
          title="הניתוח לא הופעל"
        />
      )}
      {offered ? (
        <div className="flex flex-wrap items-center gap-3">
          {ai === "missing" ? (
            <Link className={buttonClasses("primary")} to={routePaths.settings}>
              פתיחת ההגדרות
            </Link>
          ) : null}
          <Button
            disabled={operationLive || ai !== "available"}
            onClick={() => analyze.mutate()}
            pending={analyze.isPending}
            pendingLabel="מפעיל ניתוח…"
            size="default"
            variant={ai === "missing" ? "secondary" : "primary"}
          >
            ניתוח המשרה
          </Button>
          <p className="text-support text-cv-text-muted">
            {ai === "missing"
              ? "הניתוח דורש ספק AI, ועדיין לא הוגדר כזה."
              : "הניתוח כולל קריאת AI בתשלום, והעבודה מתבצעת ברקע."}
          </p>
        </div>
      ) : null}
    </section>
  );
};

/* The analysis step: the verdict on how well the reader fits the posting, and the
   requirements it was read from, with the way to the matching settings and on to the
   draft.

   While the analysis runs - on the redirect straight from creation, or a re-analysis -
   the run is the screen: it has nothing of its own to show until the result arrives, and
   a run that ends without one is reported in the same place. */
export const AnalysisPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const location = useLocation();
  const isPhone = useIsPhone();

  const query = useQuery(watchedApplicationDetailQueryOptions(applicationId));
  const detail = query.data;
  const { awaitingRecord, operation: watched, settled, watch } = useWatchedOperation(applicationId, detail);
  const { continuation } = useAutomaticDraft({ applicationId, detail, operation: watched, watch });

  const createdApplication = (location.state as { createdApplication?: CreatedApplicationState } | null)
    ?.createdApplication;
  const createdOperationId = createdApplication?.operationId ?? null;

  /* Layout, not passive: a creation redirect that already knows its Operation id must not
     paint the pending wait first for a record already sitting in cache. */
  useLayoutEffect(() => {
    if (createdOperationId !== null) watch(createdOperationId);
  }, [createdOperationId, watch]);

  const viewState = analysisViewState({
    analysisWasQueuedOnCreate: createdOperationId !== null,
    detail,
    operation: watched,
  });
  const pending = watched === undefined && viewState === "processing" ? analysisPending : undefined;
  const operationLive = isOperationLive({
    awaitingRecord,
    continuation,
    operation: watched,
    pending: pending !== undefined,
    settled,
  });
  const classification = detail === undefined ? null : classificationFromAnalysis(detail);
  /* The run is the screen while it lives, and when it ended without a result there is no
     analysis to fall back on. A failed re-analysis leaves the analysis in force on screen,
     with the run's report over it. */
  const runIsScreen =
    detail?.application.deleted_at == null &&
    (viewState === "processing" ||
      (viewState === "analysis_failed" && classification === null) ||
      (continuation !== undefined && watched?.operation_type !== "analyze_job"));

  const overlay = (
    <OperationOverlay
      awaitingRecord={awaitingRecord}
      continuation={continuation}
      eyebrow={detail === undefined ? undefined : `${detail.application.target_role} · ${detail.application.company}`}
      onQueued={watch}
      operation={watched}
      pending={pending}
      screen={runIsScreen}
      settled={settled}
    />
  );

  const draftStep = detail === undefined ? undefined : workflowDestinations(applicationId, detail).draft;
  const matchingOffered = classification !== null && matchingValuesFrom(classification) !== null;
  const actions =
    classification === null || detail?.application.deleted_at != null ? undefined : (
      <>
        {matchingOffered ? (
          <Link className={buttonClasses("secondary", "shrink-0 max-lg:px-4")} to={routePaths.matching(applicationId)}>
            <SlidersHorizontal aria-hidden="true" className="size-icon-md shrink-0" />
            הגדרות ההתאמה
          </Link>
        ) : null}
        {draftStep === undefined ? null : (
          <Link className={buttonClasses("primary", "shadow-action")} to={draftStep}>
            המשך לטיוטה
            <ChevronLeft aria-hidden="true" className="size-icon-md shrink-0" />
          </Link>
        )}
      </>
    );

  /* The overlay keeps one place in the tree whichever way the screen is drawn, so its
     session - the run, and the report it opens when the run ends - survives the swap. */
  return (
    <>
      {overlay}
      {runIsScreen ? null : (
        <StepFrame
          actions={actions}
          applicationId={applicationId}
          back={{ label: "חזרה לפרטי המועמדות", to: routePaths.application(applicationId) }}
          detail={detail}
          stage="analysis"
          title="ניתוח המשרה"
        >
          <QueryState
            error={query.error}
            errorTitle="לא ניתן לטעון את הניתוח"
            loading={detail === undefined}
            loadingState={loading}
            onRetry={() => void query.refetch()}
          >
            {detail === undefined ? null : detail.application.deleted_at ? (
              /* A deleted Application stays reachable by id so its history is never
             orphaned, but no preparation runs against it. */
              <Callout role="alert" title="המועמדות הזו נמחקה" tone="warning">
                המועמדות הוסרה מלוח המועמדויות ואין לבצע עליה פעולות הכנה נוספות. נוסח המשרה, הניתוח ומסמך קורות החיים
                נשארים בדיוק כפי שהם.
              </Callout>
            ) : (
              <div className="flex flex-col gap-3.5">
                {/* Route state only reports the exceptional creation outcome where no
                Operation exists: the analysis was asked for and refused. */}
                {createdApplication === undefined ||
                createdApplication.analysisSkipped === true ||
                createdOperationId !== null ||
                detail.preparation_state !== "needs_analysis" ||
                watched !== undefined ? null : (
                  <Callout role="alert" title="המועמדות נוצרה, אך הניתוח לא הופעל" tone="warning">
                    {problemSentence(
                      { problem: createdApplication.analysisProblem },
                      "אפשר להפעיל את הניתוח מהמסך הזה.",
                    )}
                  </Callout>
                )}

                {classification === null ? (
                  <AnalyzeFirst detail={detail} onQueued={watch} operationLive={operationLive} />
                ) : (
                  <AnalysisOverview detail={detail} onQueued={watch} operationLive={operationLive} phone={isPhone} />
                )}
              </div>
            )}
          </QueryState>
        </StepFrame>
      )}
    </>
  );
};
