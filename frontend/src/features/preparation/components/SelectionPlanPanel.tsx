import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { createSelectionPlan, selectionPlanQueryOptions } from "@/api/analyses";
import { invalidateApplicationViews } from "@/api/applications";
import type { ApplicationDetail, CreateSelectionPlanRequest } from "@/api/contracts";
import { isTerminalOperation, operationQueryKey, operationQueryOptions } from "@/api/operations";
import { aiRegenerationAvailable } from "@/api/settings";
import { useSettings } from "@/api/useSettings";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button } from "@/ui/Button";
import { QueryState } from "@/ui/QueryState";
import { surfaceClasses } from "@/ui/surface";
import { factTotals } from "../model/factGroups";
import type { WorkflowActionPlan } from "../model/workflowActionPlan";
import { FactSelectionList } from "./FactSelectionList";
import { CommitBar } from "./CommitBar";

const sameMembers = (left: readonly string[], right: readonly string[]): boolean =>
  left.length === right.length && left.every((item) => right.includes(item));

/* The reader's own overrides, and the plan they were taken against.

   Held as one value rather than three because they are one decision: an override only
   means anything against the plan it was made on. That is also what removes the effect
   this panel used to run - a plan arriving under the reader (a save, a refetch, another
   Application) made a stored `pinned`/`excluded` pair describe candidates that were no
   longer on screen, and an effect had to notice and reset it. Keeping the plan id beside
   the marks answers the same question by comparison at render: edits that name a plan
   other than the loaded one are simply not this plan's. */
interface FactOverrides {
  excluded: string[];
  pinned: string[];
  planId: string;
}

export const SelectionPlanPanel = ({
  action,
  detail,
  onQueued,
}: {
  action: NonNullable<WorkflowActionPlan["createSelectionPlan"]>;
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
}) => {
  const queryClient = useQueryClient();
  const activePlanId = action.selectionPlanId;
  const planQuery = useQuery({
    ...selectionPlanQueryOptions(activePlanId ?? ""),
    enabled: activePlanId !== null,
  });
  const { settings } = useSettings();
  const aiAvailable = aiRegenerationAvailable(settings);
  const [edits, setEdits] = useState<FactOverrides | null>(null);
  const [queuedId, setQueuedId] = useState<string | null>(null);

  const plan = planQuery.data;
  const loadedPlanId = plan?.id ?? null;
  const baseline: FactOverrides = {
    excluded: plan?.excluded_fact_ids ?? [],
    pinned: plan?.pinned_fact_ids ?? [],
    planId: loadedPlanId ?? "",
  };
  const overrides = edits !== null && loadedPlanId !== null && edits.planId === loadedPlanId ? edits : baseline;
  const { excluded, pinned } = overrides;

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
    expected_candidate_context_hash: plan?.candidate_context_hash ?? null,
    expected_facts_version: plan?.facts_version ?? null,
    expected_profile_version: plan?.profile_version ?? null,
    expected_selection_policy_version: plan?.selection_policy_version ?? null,
  });

  const finish = async () => {
    await invalidateApplicationViews(queryClient, detail.application.id);
  };
  const deterministic = useMutation({
    mutationFn: async () => createSelectionPlan(action.analysisId, request("deterministic")),
    onSuccess: finish,
  });
  const ai = useMutation({
    mutationFn: async () => {
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

  const busy = detail.active_operation != null || queuedStillRunning || deterministic.isPending || ai.isPending;
  const manualReady = activePlanId !== null && loadedPlanId === activePlanId;
  const changed = manualReady && (!sameMembers(pinned, baseline.pinned) || !sameMembers(excluded, baseline.excluded));
  const mutationError = deterministic.error ?? ai.error;

  const applyOverrides = (next: { excluded: string[]; pinned: string[] }) =>
    setEdits({ ...next, planId: loadedPlanId ?? "" });
  const togglePinned = (factId: string, checked: boolean) =>
    applyOverrides({
      excluded: checked ? excluded.filter((id) => id !== factId) : excluded,
      pinned: checked ? [...new Set([...pinned, factId])] : pinned.filter((id) => id !== factId),
    });
  const toggleExcluded = (factId: string, checked: boolean) =>
    applyOverrides({
      excluded: checked ? [...new Set([...excluded, factId])] : excluded.filter((id) => id !== factId),
      pinned: checked ? pinned.filter((id) => id !== factId) : pinned,
    });

  /* A whole section at once, expressed in the same two overrides a row uses.

     Lifting the reader's own exclusion is enough for a fact the engine had chosen -
     the plan goes back to selecting it. A fact the engine itself left out needs the pin,
     or the rebuilt plan would omit it again for the reason it already recorded. The
     omission reason is what tells the two apart, so neither is over-decided: this never
     pins a fact that was only excluded by hand. */
  const includeAll = (factIds: readonly string[]) => {
    const engineOmitted = (plan?.candidates ?? [])
      .filter((candidate) => factIds.includes(candidate.fact_id) && candidate.reason !== "excluded_by_user")
      .map((candidate) => candidate.fact_id);

    applyOverrides({
      excluded: excluded.filter((id) => !factIds.includes(id)),
      pinned: [...new Set([...pinned, ...engineOmitted])],
    });
  };

  const totals = factTotals(plan?.candidates ?? [], pinned, excluded);

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
            loading={plan === undefined}
            loadingLabel="טוען את בחירת העובדות…"
          >
            {plan === undefined ? null : (
              <FactSelectionList
                busy={busy}
                candidates={plan.candidates}
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

      <CommitBar
        primary={
          <>
            {aiAvailable ? (
              <Button
                disabled={busy || settings === undefined}
                onClick={() => ai.mutate()}
                pending={ai.isPending}
                pendingLabel="מבקש הצעת AI…"
                variant="secondary"
              >
                הצעת בחירה באמצעות AI
              </Button>
            ) : null}
            <Button
              disabled={busy || (activePlanId !== null && !changed)}
              onClick={() => deterministic.mutate()}
              pending={deterministic.isPending}
              pendingLabel="שומר את בחירת העובדות…"
              variant={action.emphasized ? "primary" : "secondary"}
            >
              {activePlanId === null ? "יצירת בחירה דטרמיניסטית" : "שמירת בחירת העובדות"}
            </Button>
          </>
        }
      >
        <p className="text-support font-medium text-cv-text-muted">
          {plan === undefined
            ? "בחירת העובדות עדיין נטענת."
            : `${totals.included} מתוך ${totals.total} עובדות ייכנסו לטיוטה.`}
          {changed ? " יש שינוי שטרם נשמר." : ""}
        </p>
      </CommitBar>
    </>
  );
};
