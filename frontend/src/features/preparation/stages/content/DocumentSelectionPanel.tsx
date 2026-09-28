import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import type { Requirement } from "@/api/analyses";
import type { ApplicationDetail, CVDocument } from "@/api/contracts";
import { invalidateDocumentViews, proposeSelection, updateSelection } from "@/api/documents";
import { operationQueryKey } from "@/api/operations";
import { aiRegenerationAvailable } from "@/api/settings";
import { useSettings } from "@/api/useSettings";
import { ActionBar } from "@/ui/ActionBar";
import { Button } from "@/ui/Button";
import { Disclosure } from "@/ui/Disclosure";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { surfaceClasses } from "@/ui/surface";
import { type FactFilter, factTotals } from "../../model/factGroups";
import { requirementsByFact } from "../../model/requirementGroups";
import { includedFactIds, noRankings, selectionChanges } from "../../model/selectionManifest";
import { AiSelectionProposal } from "./AiSelectionProposal";
import type { FactChoice } from "./FactRow";
import { FactSelectionList } from "./FactSelectionList";
import { useSelectionProposal } from "./useSelectionProposal";

const sameMembers = (left: readonly string[], right: readonly string[]): boolean =>
  left.length === right.length && left.every((item) => right.includes(item));

const rankingSteps = [
  "עובדות שמעידות על דרישת חובה במשרה קודמות לכל השאר, ואחריהן עובדות שמעידות על דרישה מועדפת.",
  "בתוך כל רמה, עובדה שתגיותיה מתאימות יותר לפרופיל ולדגש שנבחרו מדורגת גבוה יותר.",
  "אחר כך נספרות מילות המפתח מהמשרה שמופיעות בעובדה.",
  "לכל סעיף בקורות החיים יש מכסה. מה שלא נכנס למכסה לא נכלל, אלא אם הוא נדרש כדי לכסות תגית שהפרופיל מחייב.",
];

interface FactOverrides {
  documentHash: string;
  excluded: string[];
  pinned: string[];
}

/* The fact selection screen: the document's own `selection`, edited in place.

   There is no plan record to create any more. The first analysis created the document with
   the engine's deterministic selection, so this panel always opens on a selection; saving
   a change is `update_selection` against the exact document it was read from, and an AI
   proposal is `propose_selection` over the same document. With content present, the server
   updates selection and content together or refuses with a pointer to regeneration - the
   panel reports that refusal rather than second-guessing it. */
export const DocumentSelectionPanel = ({
  detail,
  document,
  emphasized,
  onQueued,
  operationLive,
  requirements,
}: {
  detail: ApplicationDetail;
  document: CVDocument;
  /* The projection recommends working on the selection now. */
  emphasized: boolean;
  onQueued: (operationId: string) => void;
  operationLive: boolean;
  requirements: readonly Requirement[];
}) => {
  const queryClient = useQueryClient();
  const applicationId = detail.application.id;
  const { settings } = useSettings();
  const aiAvailable = aiRegenerationAvailable(settings);
  const proposal = useSelectionProposal(applicationId);
  const [edits, setEdits] = useState<FactOverrides | null>(null);
  const [filter, setFilter] = useState<FactFilter>("all");

  const { selection } = document;
  const candidates = selection.candidates;
  const baseline: FactOverrides = {
    documentHash: document.document_hash,
    excluded: selection.excluded_fact_ids,
    pinned: selection.pinned_fact_ids,
  };
  /* Local marks describe the document they were made on. A document that changed under
     them - an edit, a proposal, another tab - drops them rather than carrying them onto a
     selection they were never decided against. */
  const overrides = edits !== null && edits.documentHash === document.document_hash ? edits : baseline;
  const { excluded, pinned } = overrides;

  const supportsByFact = useMemo(() => requirementsByFact(requirements), [requirements]);

  /* The AI diff is shown once the document read reflects the proposal it came from. */
  const proposalResultVisible =
    proposal.status.kind === "done" &&
    proposal.baseline !== null &&
    proposal.baseline.fromDocumentHash !== document.document_hash;
  const proposalChanges =
    proposalResultVisible && proposal.baseline !== null
      ? selectionChanges(proposal.baseline.included, candidates, baseline.pinned, baseline.excluded)
      : [];
  const changeIndex = new Map(proposalChanges.map((change) => [change.candidate.fact_id, change.direction]));

  const selectionOffered = detail.available_actions.includes("update_selection");
  const proposalOffered = detail.available_actions.includes("propose_selection");

  const save = useMutation({
    mutationFn: () =>
      updateSelection(applicationId, document.document_hash, { pinned_fact_ids: pinned, excluded_fact_ids: excluded }),
    onSuccess: async () => {
      proposal.dismiss();
      setEdits(null);
      await invalidateDocumentViews(queryClient, applicationId);
    },
  });
  const ai = useMutation({
    mutationFn: () =>
      proposeSelection(applicationId, document.document_hash, `propose-selection:${document.document_hash}`),
    onSuccess: async ({ operation }) => {
      queryClient.setQueryData(operationQueryKey(operation.id), operation);
      proposal.remember({
        fromDocumentHash: document.document_hash,
        included: includedFactIds(candidates, baseline.pinned, baseline.excluded),
        operationId: operation.id,
      });
      onQueued(operation.id);
      await invalidateDocumentViews(queryClient, applicationId);
    },
  });

  const busy =
    operationLive ||
    detail.active_operation != null ||
    proposal.status.kind === "running" ||
    save.isPending ||
    ai.isPending;
  const changed = !sameMembers(pinned, baseline.pinned) || !sameMembers(excluded, baseline.excluded);
  const mutationError = save.error ?? ai.error;

  const applyOverrides = (next: { excluded: string[]; pinned: string[] }) =>
    setEdits({ ...next, documentHash: document.document_hash });
  const choose = (factId: string, choice: FactChoice) =>
    applyOverrides({
      excluded: choice === "exclude" ? [...new Set([...excluded, factId])] : excluded.filter((id) => id !== factId),
      pinned: choice === "include" ? [...new Set([...pinned, factId])] : pinned.filter((id) => id !== factId),
    });

  // An engine-omitted fact needs a pin to come back; a hand-excluded one only needs the exclusion lifted.
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
  // Recorded only on selections activated from an AI proposal; null means "not recorded", never "not AI".
  const aiProposed = selection.proposed_by === "ai";
  const hasContent = document.content != null;

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
              המנוע דירג את כל העובדות המאושרות מול המשרה ובחר מה ייכנס לכל סעיף. אפשר להשאיר לו את ההחלטה, לכלול או
              להחריג עובדה במפורש, או לבקש הצעה מ־AI.
            </p>
          </div>
          <div className="text-end">
            <p className="text-heading-sm font-bold text-cv-text">
              {totals.included}/{totals.total}
            </p>
            <p className="text-caption text-cv-text-muted">עובדות בקורות החיים</p>
          </div>
        </div>
        <Disclosure summary="איך המנוע בוחר עובדות?">
          <ol className="flex list-decimal flex-col gap-1 ps-4">
            {rankingSteps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <p className="mt-2">
            עובדה שנכללה או הוחרגה במפורש - ידנית או בהצעת AI - גוברת על הדירוג. שינוי כאן חל על המסמך עצמו, ולכן גם על
            הטיוטה בעורך.
          </p>
        </Disclosure>
      </div>

      <AiSelectionProposal
        aiAvailable={aiAvailable}
        busy={busy}
        changes={proposalChanges}
        offered={proposalOffered}
        onDismiss={proposal.dismiss}
        onPropose={() => ai.mutate()}
        pending={ai.isPending}
        rankings={noRankings}
        rationale={aiProposed ? (selection.proposal_rationale ?? null) : undefined}
        resultVisible={proposalResultVisible}
        settingsLoaded={settings !== undefined}
        status={proposal.status}
        supportsByFact={supportsByFact}
      />

      <FactSelectionList
        aiProposed={aiProposed}
        busy={busy || !selectionOffered}
        candidates={candidates}
        changes={changeIndex}
        excluded={excluded}
        filter={filter}
        onChoose={choose}
        onFilterChange={setFilter}
        onIncludeAll={includeAll}
        pinned={pinned}
        rankings={noRankings}
        savedExcluded={baseline.excluded}
        savedPinned={baseline.pinned}
        supportsByFact={supportsByFact}
      />

      {mutationError === null ? null : (
        <ErrorCallout
          error={mutationError}
          fallbackDetail="בחירת העובדות של המסמך לא השתנתה. אפשר לרענן ולנסות שוב."
          fallbackTitle="בחירת העובדות לא נשמרה"
        />
      )}

      <ActionBar
        primary={
          <>
            {changed ? (
              <Button disabled={busy} onClick={() => setEdits(null)} variant="ghost">
                ביטול השינויים
              </Button>
            ) : null}
            <Button
              disabled={busy || !selectionOffered || !changed}
              onClick={() => save.mutate()}
              pending={save.isPending}
              pendingLabel="שומר את בחירת העובדות…"
              variant={emphasized ? "primary" : "secondary"}
            >
              שמירת בחירת העובדות
            </Button>
          </>
        }
        secondary={
          <p className="text-support font-medium text-cv-text-muted">
            {changed
              ? `${totals.included} מתוך ${totals.total} עובדות ייכנסו ${hasContent ? "למסמך" : "לטיוטה"} · יש שינוי שטרם נשמר.`
              : `${totals.included} מתוך ${totals.total} עובדות ייכנסו ${hasContent ? "למסמך" : "לטיוטה"}.`}
            {changed && hasContent ? " השמירה תעדכן גם את תוכן הטיוטה." : null}
          </p>
        }
      />
    </section>
  );
};
