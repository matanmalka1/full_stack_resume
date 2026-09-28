import type { Requirement } from "@/api/analyses";
import type { DocumentCandidate } from "@/api/contracts";
import { candidateIncluded, candidateLocked } from "./factGroups";

export type DecisionSource = "engine" | "excluded" | "locked" | "pinned";

export const decisionSource = (
  candidate: DocumentCandidate,
  pinned: readonly string[],
  excluded: readonly string[],
): DecisionSource => {
  if (candidateLocked(candidate)) {
    return "locked";
  }
  if (excluded.includes(candidate.fact_id)) {
    return "excluded";
  }
  if (pinned.includes(candidate.fact_id)) {
    return "pinned";
  }
  return "engine";
};

type SignalTone = "positive" | "neutral" | "negative";

export interface FactSignal {
  text: string;
  tone: SignalTone;
}

/* Why a fact matters to this posting, stated from the analysis: the requirements it is
   evidence for. The engine's internal ranking scores are not part of the document contract,
   so a row explains itself by requirement support alone. */
export const factSignals = (supports: readonly Requirement[]): FactSignal[] => {
  const mandatory = supports.filter((requirement) => requirement.importance === "mandatory").length;
  const other = supports.length - mandatory;
  const signals: FactSignal[] = [];
  if (mandatory > 0) {
    signals.push({
      text: mandatory === 1 ? "ראיה לדרישת חובה" : `ראיה ל־${mandatory} דרישות חובה`,
      tone: "positive",
    });
  }
  if (other > 0) {
    signals.push({
      text: other === 1 ? "ראיה לדרישה נוספת במשרה" : `ראיה ל־${other} דרישות נוספות במשרה`,
      tone: "positive",
    });
  }
  return signals;
};

export interface SelectionChange {
  candidate: DocumentCandidate;
  direction: "added" | "removed";
}

export const selectionChanges = (
  previousIncluded: readonly string[],
  candidates: readonly DocumentCandidate[],
  pinned: readonly string[],
  excluded: readonly string[],
): SelectionChange[] => {
  const before = new Set(previousIncluded);
  return candidates.flatMap((candidate): SelectionChange[] => {
    const now = candidateIncluded(candidate, pinned, excluded);
    const was = before.has(candidate.fact_id);
    if (now && !was) {
      return [{ candidate, direction: "added" }];
    }
    if (!now && was) {
      return [{ candidate, direction: "removed" }];
    }
    return [];
  });
};

export const includedFactIds = (
  candidates: readonly DocumentCandidate[],
  pinned: readonly string[],
  excluded: readonly string[],
): string[] =>
  candidates
    .filter((candidate) => candidateIncluded(candidate, pinned, excluded))
    .map((candidate) => candidate.fact_id);
