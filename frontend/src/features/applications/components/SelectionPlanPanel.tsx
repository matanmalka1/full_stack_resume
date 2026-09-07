import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { createSelectionPlan, selectionPlanQueryOptions } from "@/api/analyses";
import { invalidateApplicationViews } from "@/api/applications";
import type { ApplicationDetail, CreateSelectionPlanRequest } from "@/api/contracts";
import { isTerminalOperation, operationQueryKey, operationQueryOptions } from "@/api/operations";
import { aiRegenerationAvailable } from "@/api/settings";
import { useSettings } from "@/api/useSettings";
import { ErrorCallout } from "@/app/ErrorCallout";
import { Button } from "@/ui/Button";
import { QueryState } from "@/ui/QueryState";
import { surfaceClasses } from "@/ui/Surface";
import { applicationActionPlan } from "./applicationActionPlan";
import { FactSelectionList } from "./preparation/FactSelectionList";
import { PreparationActionBar } from "./preparation/PreparationActionBar";
import { factTotals } from "./preparation/factGroups";

const sameMembers = (left: readonly string[], right: readonly string[]): boolean =>
  left.length === right.length && left.every((item) => right.includes(item));

export const SelectionPlanPanel = ({
  detail,
  onQueued,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
}) => {
  const queryClient = useQueryClient();
  const action = applicationActionPlan(detail).createSelectionPlan;
  const activePlanId = action?.selectionPlanId ?? null;
  const planQuery = useQuery({
    ...selectionPlanQueryOptions(activePlanId ?? ""),
    enabled: action !== null && activePlanId !== null,
  });
  const { settings } = useSettings();
  const aiAvailable = aiRegenerationAvailable(settings);
  const [pinned, setPinned] = useState<string[]>([]);
  const [excluded, setExcluded] = useState<string[]>([]);
  const [editingPlanId, setEditingPlanId] = useState<string | null>(null);
  const [queuedId, setQueuedId] = useState<string | null>(null);

  const baselinePinned = useMemo(() => planQuery.data?.pinned_fact_ids ?? [], [planQuery.data]);
  const baselineExcluded = useMemo(() => planQuery.data?.excluded_fact_ids ?? [], [planQuery.data]);

  useEffect(() => {
    setPinned(baselinePinned);
    setExcluded(baselineExcluded);
    setEditingPlanId(planQuery.data?.id ?? null);
  }, [activePlanId, baselineExcluded, baselinePinned, planQuery.data?.id]);

  const queuedQuery = useQuery({
    ...operationQueryOptions(queuedId ?? ""),
    enabled: queuedId !== null,
  });
  const queuedStillRunning = queuedId !== null && !isTerminalOperation(queuedQuery.data);

  const request = (mode: CreateSelectionPlanRequest["mode"]): CreateSelectionPlanRequest => ({
    application_id: detail.application.id,
    mode,
    pinned_fact_ids: mode === "ai" ? [] : pinned,
    excluded_fact_ids: mode === "ai" ? [] : excluded,
    accepted_requirement_ids: [],
    acceptance_reason: null,
    expected_selection_plan_id: activePlanId,
    expected_candidate_context_hash: planQuery.data?.candidate_context_hash ?? null,
    expected_facts_version: planQuery.data?.facts_version ?? null,
    expected_profile_version: planQuery.data?.profile_version ?? null,
    expected_selection_policy_version: planQuery.data?.selection_policy_version ?? null,
  });

  const finish = async () => {
    await invalidateApplicationViews(queryClient, detail.application.id);
  };
  const deterministic = useMutation({
    mutationFn: async () => {
      if (action === null) throw new Error("create_selection_plan was not offered for the active analysis");
      return createSelectionPlan(action.analysisId, request("deterministic"));
    },
    onSuccess: finish,
  });
  const ai = useMutation({
    mutationFn: async () => {
      if (action === null) throw new Error("create_selection_plan was not offered for the active analysis");
      const key = `selection-plan:${detail.application.id}:${action.analysisId}:${activePlanId ?? "none"}:ai`;
      return createSelectionPlan(action.analysisId, request("ai"), key);
    },
    onSuccess: async (created) => {
      if (created.kind === "queued") {
        queryClient.setQueryData(operationQueryKey(created.operation.id), created.operation);
        setQueuedId(created.operation.id);
        onQueued(created.operation.id);
      }
      await finish();
    },
  });

  if (action === null) return null;

  const busy = detail.active_operation != null || queuedStillRunning || deterministic.isPending || ai.isPending;
  const manualReady = activePlanId !== null && editingPlanId === activePlanId && planQuery.data !== undefined;
  const changed = manualReady && (!sameMembers(pinned, baselinePinned) || !sameMembers(excluded, baselineExcluded));
  const mutationError = deterministic.error ?? ai.error;

  const togglePinned = (factId: string, checked: boolean) => {
    setPinned((current) => (checked ? [...new Set([...current, factId])] : current.filter((id) => id !== factId)));
    if (checked) setExcluded((current) => current.filter((id) => id !== factId));
  };
  const toggleExcluded = (factId: string, checked: boolean) => {
    setExcluded((current) => (checked ? [...new Set([...current, factId])] : current.filter((id) => id !== factId)));
    if (checked) setPinned((current) => current.filter((id) => id !== factId));
  };

  /* A whole section at once, expressed in the same two overrides a row uses.

     Lifting the reader's own exclusion is enough for a fact the engine had chosen -
     the plan goes back to selecting it. A fact the engine itself left out needs the pin,
     or the rebuilt plan would omit it again for the reason it already recorded. The
     omission reason is what tells the two apart, so neither is over-decided: this never
     pins a fact that was only excluded by hand. */
  const includeAll = (factIds: readonly string[]) => {
    const engineOmitted = new Set(
      (planQuery.data?.candidates ?? [])
        .filter((candidate) => factIds.includes(candidate.fact_id) && candidate.reason !== "excluded_by_user")
        .map((candidate) => candidate.fact_id),
    );
    setExcluded((current) => current.filter((id) => !factIds.includes(id)));
    setPinned((current) => [...new Set([...current, ...[...engineOmitted]])]);
  };

  const deterministicLabel = activePlanId === null ? "יצירת בחירה דטרמיניסטית" : "שמירת בחירת העובדות";
  const deterministicButton = (
    <Button
      disabled={busy || (activePlanId !== null && !changed)}
      onClick={() => deterministic.mutate()}
      pending={deterministic.isPending}
      pendingLabel="שומר את בחירת העובדות…"
      variant={action.emphasized ? "primary" : "secondary"}
    >
      {deterministicLabel}
    </Button>
  );
  const aiButton = aiAvailable ? (
    <Button
      disabled={busy || settings === undefined}
      onClick={() => ai.mutate()}
      pending={ai.isPending}
      pendingLabel="מבקש הצעת AI…"
      variant="secondary"
    >
      הצעת בחירה באמצעות AI
    </Button>
  ) : null;

  const totals = factTotals(planQuery.data?.candidates ?? [], pinned, excluded);

  return (
    <>
      <section
        aria-labelledby="selection-plan-heading"
        className={surfaceClasses("flex flex-col gap-4 bg-cv-surface p-5")}
      >
        <div>
          <h2 className="text-body font-semibold text-cv-text" id="selection-plan-heading">
            בחירת העובדות לקורות החיים
          </h2>
          <p className="mt-1 text-support leading-6 text-cv-text-muted">
            {activePlanId === null
              ? "לניתוח הפעיל אין תוכנית בחירה. אפשר ליצור את בחירת ברירת המחדל או לבקש מ־AI להציע אחת."
              : "התוכנית הדטרמיניסטית פעילה. אפשר לקבע או להחריג עובדות לפני יצירת הטיוטה, או לבקש הצעת AI חלופית."}
          </p>
        </div>

        {activePlanId === null ? null : (
          <QueryState
            error={planQuery.error}
            fallbackDetail="לא ניתן לקרוא את העובדות שהתוכנית שקלה. התוכנית הפעילה לא השתנתה."
            fallbackTitle="בחירת העובדות לא נטענה"
            loading={planQuery.data === undefined}
            loadingLabel="טוען את בחירת העובדות…"
          >
            {planQuery.data === undefined ? null : (
              <FactSelectionList
                busy={busy}
                candidates={planQuery.data.candidates}
                excluded={excluded}
                onIncludeAll={includeAll}
                onToggleExcluded={toggleExcluded}
                onTogglePinned={togglePinned}
                pinned={pinned}
              />
            )}
          </QueryState>
        )}

        {mutationError === null ? null : (
          <ErrorCallout
            error={mutationError}
            fallbackDetail="תוכנית הבחירה הפעילה לא השתנתה. אפשר לרענן ולנסות שוב."
            fallbackTitle="בחירת העובדות לא נשמרה"
          />
        )}

        {!aiAvailable && settings !== undefined ? (
          <p className="text-support text-cv-text-muted">הצעת AI זמינה לאחר הפעלת AI והגדרת ספק במסך ההגדרות.</p>
        ) : null}
      </section>

      <PreparationActionBar
        primary={
          <>
            {aiButton}
            {deterministicButton}
          </>
        }
      >
        <p className="text-support font-medium text-cv-text-muted">
          {planQuery.data === undefined
            ? "בחירת העובדות עדיין נטענת."
            : `${totals.included} מתוך ${totals.total} עובדות ייכנסו לטיוטה.`}
          {changed ? " יש שינוי שטרם נשמר." : ""}
        </p>
      </PreparationActionBar>
    </>
  );
};
