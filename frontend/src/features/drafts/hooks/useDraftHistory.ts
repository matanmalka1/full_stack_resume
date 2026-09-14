import { useCallback, useMemo, useState } from "react";

import type { DraftClaim, WorkingDraft } from "@/api/contracts";

const HISTORY_LIMIT = 50;
const TYPING_GROUP_MS = 900;

type Outline = WorkingDraft["outline"];
type HistoryEntry = { before: Outline; after: Outline; claimId: string | null; at: number };
type HistoryState = {
  draftId: string | null;
  sourceKey: string | null;
  outline: Outline | null;
  past: HistoryEntry[];
  future: HistoryEntry[];
};

const copyOutline = (outline: Outline): Outline => structuredClone(outline);

const claimMap = (outline: Outline): Map<string, DraftClaim> =>
  new Map(
    [outline.headline, ...outline.contacts, ...outline.sections.flatMap((section) => section.claims)].map((claim) => [
      claim.claim_id,
      claim,
    ]),
  );

interface DraftHistoryOptions {
  draft: WorkingDraft | undefined;
  queueClaimOrder: (section: string, order: string[]) => void;
  queueEdit: (claim: DraftClaim, text: string) => void;
  queueSectionOrder: (order: string[]) => void;
}

export const useDraftHistory = ({ draft, queueClaimOrder, queueEdit, queueSectionOrder }: DraftHistoryOptions) => {
  /* Include the outline as well as its server identity. A cache refresh may replace the
     structured projection without changing the hook instance, and that replacement must
     become the new visible base without discarding this draft's usable history. */
  const sourceKey =
    draft === undefined
      ? null
      : `${draft.id}:${draft.edit_version}:${draft.content_hash}:${JSON.stringify(draft.outline)}`;
  const [stored, setStored] = useState<HistoryState>(() => ({
    draftId: draft?.id ?? null,
    sourceKey,
    outline: draft === undefined ? null : copyOutline(draft.outline),
    past: [],
    future: [],
  }));
  let history = stored;
  if (stored.sourceKey !== sourceKey) {
    history = {
      draftId: draft?.id ?? null,
      sourceKey,
      outline: draft === undefined ? null : copyOutline(draft.outline),
      past: stored.draftId === draft?.id ? stored.past : [],
      future: stored.draftId === draft?.id ? stored.future : [],
    };
    setStored(history);
  }

  const record = useCallback((next: Outline, claimId: string | null) => {
    setStored((currentHistory) => {
      const current = currentHistory.outline;
      if (current === null) return currentHistory;
      const now = Date.now();
      const last = currentHistory.past.at(-1);
      const past =
        claimId !== null && last?.claimId === claimId && now - last.at <= TYPING_GROUP_MS
          ? [...currentHistory.past.slice(0, -1), { ...last, after: copyOutline(next), at: now }]
          : [
              ...currentHistory.past,
              { before: copyOutline(current), after: copyOutline(next), claimId, at: now },
            ].slice(-HISTORY_LIMIT);
      return { ...currentHistory, outline: next, past, future: [] };
    });
  }, []);

  const edit = useCallback(
    (claim: DraftClaim, text: string) => {
      const current = history.outline;
      if (current === null) return;
      const next = copyOutline(current);
      const target = claimMap(next).get(claim.claim_id);
      if (target === undefined || target.text === text) return;
      target.text = text;
      record(next, claim.claim_id);
      queueEdit(claim, text);
    },
    [history.outline, queueEdit, record],
  );

  const moveSection = useCallback(
    (index: number, offset: -1 | 1) => {
      const current = history.outline;
      if (current === null || index + offset < 0 || index + offset >= current.sections.length) return;
      const next = copyOutline(current);
      [next.sections[index], next.sections[index + offset]] = [next.sections[index + offset], next.sections[index]];
      record(next, null);
      queueSectionOrder(next.sections.map((section) => section.name));
    },
    [history.outline, queueSectionOrder, record],
  );

  const moveClaim = useCallback(
    (sectionName: string, index: number, offset: -1 | 1) => {
      const current = history.outline;
      if (current === null) return;
      const section = current.sections.find((candidate) => candidate.name === sectionName);
      if (section === undefined || index + offset < 0 || index + offset >= section.claims.length) return;
      const next = copyOutline(current);
      const nextSection = next.sections.find((candidate) => candidate.name === sectionName);
      if (nextSection === undefined) return;
      [nextSection.claims[index], nextSection.claims[index + offset]] = [
        nextSection.claims[index + offset],
        nextSection.claims[index],
      ];
      record(next, null);
      queueClaimOrder(
        sectionName,
        nextSection.claims.map((claim) => claim.claim_id),
      );
    },
    [history.outline, queueClaimOrder, record],
  );

  const apply = useCallback(
    (target: Outline) => {
      const current = history.outline;
      if (current === null) return;
      const currentClaims = claimMap(current);
      for (const claim of claimMap(target).values()) {
        const previous = currentClaims.get(claim.claim_id);
        if (previous !== undefined && previous.text !== claim.text) queueEdit(previous, claim.text);
      }
      if (
        current.sections.map((section) => section.name).join("\0") !==
        target.sections.map((section) => section.name).join("\0")
      ) {
        queueSectionOrder(target.sections.map((section) => section.name));
      }
      for (const section of target.sections) {
        const previous = current.sections.find((candidate) => candidate.name === section.name);
        if (
          previous !== undefined &&
          previous.claims.map((claim) => claim.claim_id).join("\0") !==
            section.claims.map((claim) => claim.claim_id).join("\0")
        ) {
          queueClaimOrder(
            section.name,
            section.claims.map((claim) => claim.claim_id),
          );
        }
      }
    },
    [history.outline, queueClaimOrder, queueEdit, queueSectionOrder],
  );

  const undo = useCallback(() => {
    const entry = history.past.at(-1);
    if (entry === undefined) return;
    apply(entry.before);
    setStored({
      ...history,
      outline: copyOutline(entry.before),
      past: history.past.slice(0, -1),
      future: [entry, ...history.future],
    });
  }, [apply, history]);

  const redo = useCallback(() => {
    const entry = history.future[0];
    if (entry === undefined) return;
    apply(entry.after);
    setStored({
      ...history,
      outline: copyOutline(entry.after),
      past: [...history.past, entry].slice(-HISTORY_LIMIT),
      future: history.future.slice(1),
    });
  }, [apply, history]);

  const reset = useCallback(() => {
    setStored({
      draftId: draft?.id ?? null,
      sourceKey,
      outline: draft === undefined ? null : copyOutline(draft.outline),
      past: [],
      future: [],
    });
  }, [draft, sourceKey]);

  const visibleDraft = useMemo(
    () => (draft === undefined || history.outline === null ? draft : { ...draft, outline: history.outline }),
    [draft, history.outline],
  );

  return {
    canRedo: history.future.length > 0,
    canUndo: history.past.length > 0,
    edit,
    moveClaim,
    moveSection,
    redo,
    reset,
    undo,
    visibleDraft,
  };
};
