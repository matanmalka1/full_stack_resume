import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { createSelectionPlan, selectionPlanQueryOptions } from "../../api/analyses";
import { invalidateApplicationViews } from "../../api/applications";
import type { ApplicationDetail, CreateSelectionPlanRequest, SelectionPlanCandidate } from "../../api/contracts";
import { isTerminalOperation, operationQueryKey, operationQueryOptions } from "../../api/operations";
import { aiRegenerationAvailable } from "../../api/settings";
import { useSettings } from "../../api/useSettings";
import { ErrorCallout } from "../../app/ErrorCallout";
import { ActionBar } from "../../ui/ActionBar";
import { Button } from "../../ui/Button";
import { Checkbox } from "../../ui/Checkbox";
import { Disclosure } from "../../ui/Disclosure";
import { QueryState } from "../../ui/QueryState";
import { omissionReasonLabels, selectionOutcomeLabels } from "../draft-editor/draftLabels";
import { applicationActionPlan } from "./applicationActionPlan";

const sameMembers = (left: readonly string[], right: readonly string[]): boolean =>
  left.length === right.length && left.every((item) => right.includes(item));

const factLabel = (candidate: SelectionPlanCandidate): string => candidate.text ?? "לא ניתן לקרוא את העובדה הזו מהידע.";

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

  return (
    <section aria-labelledby="selection-plan-heading" className="flex flex-col gap-4 border-b border-cv-border pb-5">
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
            <Disclosure summary={`בדיקת ${planQuery.data.candidates.length} העובדות שהתוכנית שקלה`}>
              <ul className="flex flex-col divide-y divide-cv-border">
                {planQuery.data.candidates.map((candidate) => (
                  <li className="flex flex-col gap-2 py-3" key={candidate.fact_id}>
                    <div>
                      <p className="text-body text-cv-text" dir="auto">
                        {factLabel(candidate)}
                      </p>
                      <p className="text-support text-cv-text-muted">
                        {selectionOutcomeLabels[candidate.outcome]}
                        {candidate.reason == null ? "" : ` · ${omissionReasonLabels[candidate.reason]}`}
                        {` · ${candidate.section}`}
                      </p>
                    </div>
                    {candidate.user_selectable ? (
                      <div className="flex flex-wrap gap-2">
                        <Checkbox
                          checked={pinned.includes(candidate.fact_id)}
                          disabled={busy || candidate.text == null}
                          onChange={(event) => togglePinned(candidate.fact_id, event.target.checked)}
                        >
                          קיבוע העובדה
                        </Checkbox>
                        <Checkbox
                          checked={excluded.includes(candidate.fact_id)}
                          disabled={busy || candidate.text == null}
                          onChange={(event) => toggleExcluded(candidate.fact_id, event.target.checked)}
                        >
                          החרגת העובדה
                        </Checkbox>
                      </div>
                    ) : (
                      <p className="text-support text-cv-text-muted">רכיב מבני שנשמר לפי כללי המסמך.</p>
                    )}
                  </li>
                ))}
              </ul>
            </Disclosure>
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

      <ActionBar align="start" primary={deterministicButton} secondary={aiButton ?? undefined} />
    </section>
  );
};
