import { useQuery } from "@tanstack/react-query";

import { watchedApplicationDetailQueryOptions } from "@/api/applications";
import { OperationOverlay, isOperationLive, useWatchedOperation } from "@/features/operations";
import { useIsPhone } from "@/ui/useIsPhone";
import { routePaths } from "@/navigation/routePaths";
import { useRequiredParam } from "@/navigation/useRequiredParam";
import { Callout } from "@/ui/Callout";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { useAutomaticDraft } from "../api/mutations";
import { StepFrame } from "../components/StepFrame";
import { workflowActionPlan } from "../model/workflowActionPlan";
import { NextStepPanel } from "../stages/verification/NextStepPanel";

const loading = (
  <div className="flex flex-col gap-4">
    <LiveRegion>טוען את פרטי המועמדות…</LiveRegion>
    <Skeleton className="block h-40 w-full" />
  </div>
);

/* The step between the analysis and the editor: the action the workflow is waiting on -
   usually creating the draft - what stands in its way, and the other actions on offer.

   A draft being written is the screen while it runs, as the analysis is on the step
   before: there is nothing of this step's own to show until the editor has a draft, and
   the screen moves on to it by itself when the draft arrives. */
export const VerificationPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const isPhone = useIsPhone();
  const query = useQuery(watchedApplicationDetailQueryOptions(applicationId));
  const detail = query.data;
  const { awaitingRecord, operation: watched, settled, watch } = useWatchedOperation(applicationId, detail);
  const { continuation } = useAutomaticDraft({ applicationId, detail, operation: watched, watch });
  const operationLive = isOperationLive({ awaitingRecord, continuation, operation: watched, pending: false, settled });
  /* Only live work takes the screen. A run that ended is reported by the overlay's own
     report over the step, which still offers every way on. */
  const runIsScreen = operationLive && detail?.application.deleted_at == null;

  /* The overlay keeps one place in the tree whichever way the screen is drawn, so its
     session - the run, and the report it opens when the run ends - survives the swap. */
  return (
    <>
      <OperationOverlay
        awaitingRecord={awaitingRecord}
        continuation={continuation}
        eyebrow={detail === undefined ? undefined : `${detail.application.target_role} · ${detail.application.company}`}
        onQueued={watch}
        operation={watched}
        screen={runIsScreen}
        settled={settled}
      />
      {runIsScreen ? null : (
        <StepFrame
          applicationId={applicationId}
          back={{ label: "חזרה לניתוח המשרה", to: routePaths.analysis(applicationId) }}
          detail={detail}
          stage="draft"
          title="טיוטה ואימות"
        >
          <QueryState
            error={query.error}
            errorTitle="לא ניתן לטעון את פרטי המועמדות"
            loading={detail === undefined}
            loadingState={loading}
            onRetry={() => void query.refetch()}
          >
            {detail === undefined ? null : detail.application.deleted_at ? (
              <Callout role="alert" title="המועמדות הזו נמחקה" tone="warning">
                המועמדות הוסרה מלוח המועמדויות ואין לבצע עליה פעולות הכנה נוספות. נוסח המשרה, הניתוח ומסמך קורות החיים
                נשארים בדיוק כפי שהם.
              </Callout>
            ) : (
              <NextStepPanel
                detail={detail}
                onQueued={watch}
                operationLive={operationLive}
                phone={isPhone}
                plan={workflowActionPlan(detail)}
              />
            )}
          </QueryState>
        </StepFrame>
      )}
    </>
  );
};
