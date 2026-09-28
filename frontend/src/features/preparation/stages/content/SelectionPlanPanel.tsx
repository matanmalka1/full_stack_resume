import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { type Requirement, createSelectionPlan, selectionPlanQueryOptions } from "@/api/analyses";
import { invalidateApplicationViews } from "@/api/applications";
import type { ApplicationDetail, CreateSelectionPlanRequest } from "@/api/contracts";
import { operationQueryKey } from "@/api/operations";
import { aiRegenerationAvailable } from "@/api/settings";
import { useSettings } from "@/api/useSettings";
import { ActionBar } from "@/ui/ActionBar";
import { Button } from "@/ui/Button";
import { Disclosure } from "@/ui/Disclosure";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { QueryState } from "@/ui/QueryState";
import { surfaceClasses } from "@/ui/surface";
import { type FactFilter, factTotals } from "../../model/factGroups";
import { requirementsByFact } from "../../model/requirementGroups";
import { factRankings, includedFactIds, selectionChanges } from "../../model/selectionManifest";
import type { WorkflowActionPlan } from "../../model/workflowActionPlan";
import { AiSelectionProposal } from "./AiSelectionProposal";
import type { FactChoice } from "./FactRow";
import { FactSelectionList } from "./FactSelectionList";
import { useSelectionProposal } from "./useSelectionProposal";

const sameMembers = (left: readonly string[], right: readonly string[]): boolean =>
  left.length === right.length && left.every((item) => right.includes(item));

/* The engine's ranking, in the order it applies it. Stated once, beside the list it
   explains, so the per-fact reasons below read as terms of one rule rather than as
   unrelated remarks. */
const rankingSteps = [
  "עובדות שמעידות על דרישת חובה במשרה קודמות לכל השאר, ואחריהן עובדות שמעידות על דרישה מועדפת.",
  "בתוך כל רמה, עובדה שתגיותיה מתאימות יותר לפרופיל ולדגש שנבחרו מדורגת גבוה יותר.",
  "אחר כך נספרות מילות המפתח מהמשרה שמופיעות בעובדה.",
  "לכל סעיף בקורות החיים יש מכסה. מה שלא נכנס למכסה לא נכלל, אלא אם הוא נדרש כדי לכסות תגית שהפרופיל מחייב.",
];

/* The reader's own overrides, and the plan they were taken against.

   Held as one value rather than three because they are one decision: an override only
   means anything against the plan it was made on. Edits that name a plan other than the
   loaded one are simply not this plan's, so a plan arriving under the reader (a save, a
   refetch, a finished AI proposal) resets them by comparison rather than by an effect. */
interface FactOverrides {
  excluded: string[];
  pinned: string[];
  planId: string;
}

export const SelectionPlanPanel = ({
  action,
  detail,
  onQueued,
  operationLive,
  requirements,
}: {
  action: NonNullable<WorkflowActionPlan["createSelectionPlan"]>;
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  /* Whether this Application's work is under way, by `isOperationLive`: the actions that
     change what a run replaces wait for it, whether or not its overlay is showing. */
  operationLive: boolean;
  /* The active analysis' requirements, so each fact can say which of them it answers. */
  requirements: readonly Requirement[];
}) => {
  const queryClient = useQueryClient();
  const activePlanId = action.selectionPlanId;
  const planQuery = useQuery({
    ...selectionPlanQueryOptions(activePlanId ?? ""),
    enabled: activePlanId !== null,
  });
  const { settings } = useSettings();
  const aiAvailable = aiRegenerationAvailable(settings);
  const proposal = useSelectionProposal(detail.application.id);
  const [edits, setEdits] = useState<FactOverrides | null>(null);
  const [filter, setFilter] = useState<FactFilter>("all");

  const plan = planQuery.data;
  const candidates = plan?.candidates ?? [];
  const loadedPlanId = plan?.id ?? null;
  const baseline: FactOverrides = {
    excluded: plan?.excluded_fact_ids ?? [],
    pinned: plan?.pinned_fact_ids ?? [],
    planId: loadedPlanId ?? "",
  };
  const overrides = edits !== null && loadedPlanId !== null && edits.planId === loadedPlanId ? edits : baseline;
  const { excluded, pinned } = overrides;

  const rankings = useMemo(() => factRankings(plan?.plan), [plan]);
  const supportsByFact = useMemo(() => requirementsByFact(requirements), [requirements]);

  /* The finished proposal's changes, against the selection the reader had when asking.
     Only while its plan is the one on screen: once another plan replaces it (a manual
     save, a second proposal), "what the AI changed" is no longer what this list shows. */
  const proposalResultVisible =
    proposal.status.kind === "done" &&
    proposal.status.resultPlanId !== null &&
    proposal.status.resultPlanId === loadedPlanId;
  const proposalFirstPlan = proposal.baseline?.fromPlanId === null;
  const proposalChanges =
    proposalResultVisible && proposal.baseline !== null && !proposalFirstPlan
      ? selectionChanges(proposal.baseline.included, candidates, baseline.pinned, baseline.excluded)
      : [];
  const changeIndex = new Map(proposalChanges.map((change) => [change.candidate.fact_id, change.direction]));

  const request = (mode: CreateSelectionPlanRequest["mode"]): CreateSelectionPlanRequest => ({
    application_id: detail.application.id,
    mode,
    pinned_fact_ids: mode === "ai" ? [] : pinned,
    excluded_fact_ids: mode === "ai" ? [] : excluded,
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
    onSuccess: async () => {
      proposal.dismiss();
      await finish();
    },
  });
  const ai = useMutation({
    mutationFn: async () => {
      const key = `selection-plan:${detail.application.id}:${action.analysisId}:${activePlanId ?? "none"}:ai`;
      return createSelectionPlan(action.analysisId, request("ai"), key);
    },
    onSuccess: async (created) => {
      if (created.kind === "queued") {
        queryClient.setQueryData(operationQueryKey(created.operation.id), created.operation);
        proposal.remember({
          fromPlanId: loadedPlanId,
          included: includedFactIds(candidates, baseline.pinned, baseline.excluded),
          operationId: created.operation.id,
        });
        onQueued(created.operation.id);
      }
      await finish();
    },
  });

  const busy =
    operationLive ||
    detail.active_operation != null ||
    proposal.status.kind === "running" ||
    deterministic.isPending ||
    ai.isPending;
  const manualReady = activePlanId !== null && loadedPlanId === activePlanId;
  const changed = manualReady && (!sameMembers(pinned, baseline.pinned) || !sameMembers(excluded, baseline.excluded));
  const mutationError = deterministic.error ?? ai.error;

  const applyOverrides = (next: { excluded: string[]; pinned: string[] }) =>
    setEdits({ ...next, planId: loadedPlanId ?? "" });
  const choose = (factId: string, choice: FactChoice) =>
    applyOverrides({
      excluded: choice === "exclude" ? [...new Set([...excluded, factId])] : excluded.filter((id) => id !== factId),
      pinned: choice === "include" ? [...new Set([...pinned, factId])] : pinned.filter((id) => id !== factId),
    });

  /* A whole section at once, expressed in the same two overrides a row uses.

     Lifting the reader's own exclusion is enough for a fact the engine had chosen - the
     plan goes back to selecting it. A fact the engine itself left out needs the pin, or
     the rebuilt plan would omit it again for the reason it already recorded. The omission
     reason is what tells the two apart, so this never pins a fact that was only excluded
     by hand. */
  const includeAll = (factIds: readonly string[]) => {
    const engineOmitted = candidates
      .filter((candidate) => factIds.includes(candidate.fact_id) && candidate.reason !== "excluded_by_user")
      .map((candidate) => candidate.fact_id);

    applyOverrides({
      excluded: excluded.filter((id) => !factIds.includes(id)),
      pinned: [...new Set([...pinned, ...engineOmitted])],
    });
  };

  const totals = factTotals(candidates, pinned, excluded);

  return (
    <section
      aria-labelledby="selection-plan-heading"
      className={surfaceClasses("flex flex-col gap-5 bg-cv-surface p-5")}
    >
      <div className="flex flex-col gap-3 border-b border-cv-border pb-4">
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-2">
          <div className="min-w-0">
            <h2 className="text-heading-sm font-bold text-cv-text" id="selection-plan-heading">
              בחירת העובדות לקורות החיים
            </h2>
            <p className="mt-1 max-w-2xl text-support text-cv-text-muted">
              {activePlanId === null
                ? "לניתוח הפעיל אין עדיין בחירת עובדות. אפשר ליצור את בחירת המנוע, או לבקש מ־AI להציע אחת."
                : "המנוע דירג את כל העובדות המאושרות מול המשרה ובחר מה ייכנס לכל סעיף. אפשר להשאיר לו את ההחלטה, לכלול או להחריג עובדה במפורש, או לבקש הצעה מ־AI."}
            </p>
          </div>
          {plan === undefined ? null : (
            <div className="text-end">
              <p className="text-heading-sm font-bold text-cv-text">
                {totals.included}/{totals.total}
              </p>
              <p className="text-caption text-cv-text-muted">עובדות בקורות החיים</p>
            </div>
          )}
        </div>
        <Disclosure summary="איך המנוע בוחר עובדות?">
          <ol className="flex list-decimal flex-col gap-1 ps-4">
            {rankingSteps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <p className="mt-2">
            ליד כל עובדה מוצגים השיקולים שהובילו להחלטה. עובדה שנכללה או הוחרגה במפורש - ידנית או בהצעת AI - גוברת על
            הדירוג. שינוי כאן חל גם בעורך הטיוטה, בכרטיס "ביסוס עובדתי".
          </p>
        </Disclosure>
      </div>

      <AiSelectionProposal
        aiAvailable={aiAvailable}
        busy={busy}
        changes={proposalChanges}
        firstPlan={proposalFirstPlan}
        onDismiss={proposal.dismiss}
        onPropose={() => ai.mutate()}
        pending={ai.isPending}
        rankings={rankings}
        resultVisible={proposalResultVisible}
        settingsLoaded={settings !== undefined}
        status={proposal.status}
        supportsByFact={supportsByFact}
      />

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
              candidates={candidates}
              changes={changeIndex}
              excluded={excluded}
              filter={filter}
              onChoose={choose}
              onFilterChange={setFilter}
              onIncludeAll={includeAll}
              pinned={pinned}
              rankings={rankings}
              savedExcluded={baseline.excluded}
              savedPinned={baseline.pinned}
              supportsByFact={supportsByFact}
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

      {/* This saves a refinement inside the preparation step; it does not advance the
          wizard. Kept local and non-sticky so it cannot compete with the step's one
          viewport commit bar. */}
      <ActionBar
        primary={
          <>
            {changed ? (
              <Button disabled={busy} onClick={() => setEdits(null)} variant="ghost">
                ביטול השינויים
              </Button>
            ) : null}
            <Button
              disabled={busy || (activePlanId !== null && !changed)}
              onClick={() => deterministic.mutate()}
              pending={deterministic.isPending}
              pendingLabel="שומר את בחירת העובדות…"
              variant={action.emphasized ? "primary" : "secondary"}
            >
              {activePlanId === null ? "יצירת בחירת ברירת המחדל" : "שמירת בחירת העובדות"}
            </Button>
          </>
        }
        secondary={
          <p className="text-support font-medium text-cv-text-muted">
            {activePlanId === null
              ? "אין עדיין בחירה שמורה."
              : plan === undefined
                ? "בחירת העובדות עדיין נטענת."
                : changed
                  ? `${totals.included} מתוך ${totals.total} עובדות ייכנסו לטיוטה · יש שינוי שטרם נשמר.`
                  : `${totals.included} מתוך ${totals.total} עובדות ייכנסו לטיוטה.`}
          </p>
        }
      />
    </section>
  );
};
