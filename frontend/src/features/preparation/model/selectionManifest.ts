import type { Requirement } from "@/api/analyses";
import type { SelectionPlanCandidate } from "@/api/contracts";
import { candidateIncluded, candidateLocked } from "./factGroups";

export interface FactRanking {
  emphasisScore: number;
  gapSubstitute: boolean;
  keywordHits: number;
  profileScore: number;
  requirementRank: number;
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null;

const count = (value: unknown): number => (typeof value === "number" && Number.isFinite(value) ? value : 0);

// The manifest is an opaque object on the wire, so it is narrowed field by field.
export const factRankings = (manifest: unknown): Map<string, FactRanking> => {
  const rankings = new Map<string, FactRanking>();
  if (!isRecord(manifest) || !Array.isArray(manifest.candidates)) {
    return rankings;
  }
  for (const candidate of manifest.candidates) {
    if (!isRecord(candidate) || typeof candidate.fact_id !== "string") {
      continue;
    }
    rankings.set(candidate.fact_id, {
      emphasisScore: count(candidate.emphasis_score),
      gapSubstitute: candidate.gap_substitute === true,
      keywordHits: count(candidate.keyword_hits),
      profileScore: count(candidate.profile_score),
      requirementRank: count(candidate.requirement_rank),
    });
  }
  return rankings;
};

export type DecisionSource = "engine" | "excluded" | "locked" | "pinned";

export const decisionSource = (
  candidate: SelectionPlanCandidate,
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

export const factSignals = (ranking: FactRanking | undefined, supports: readonly Requirement[]): FactSignal[] => {
  const signals: FactSignal[] = [];
  const mandatory = supports.filter((requirement) => requirement.importance === "mandatory").length;
  const other = supports.length - mandatory;

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
  if (supports.length === 0 && ranking !== undefined && ranking.requirementRank > 0) {
    signals.push({
      text: ranking.requirementRank >= 2 ? "ראיה לדרישת חובה" : "ראיה לדרישה מועדפת",
      tone: "positive",
    });
  }
  if (ranking === undefined) {
    return signals;
  }
  if (ranking.gapSubstitute) {
    signals.push({ text: "מוצעת כחלופה לדרישה שאינה מכוסה", tone: "neutral" });
  }
  const semantic = ranking.profileScore + ranking.emphasisScore;
  signals.push(
    semantic > 0
      ? { text: `רלוונטית לפרופיל ולדגש (ציון ${semantic})`, tone: "positive" }
      : { text: "לא רלוונטית לפרופיל ולדגש הנוכחיים", tone: "negative" },
  );
  if (ranking.keywordHits > 0) {
    signals.push({
      text: ranking.keywordHits === 1 ? "מכילה מילת מפתח מהמשרה" : `מכילה ${ranking.keywordHits} מילות מפתח מהמשרה`,
      tone: "positive",
    });
  }
  return signals;
};

export interface SelectionChange {
  candidate: SelectionPlanCandidate;
  direction: "added" | "removed";
}

export const selectionChanges = (
  previousIncluded: readonly string[],
  candidates: readonly SelectionPlanCandidate[],
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
  candidates: readonly SelectionPlanCandidate[],
  pinned: readonly string[],
  excluded: readonly string[],
): string[] =>
  candidates
    .filter((candidate) => candidateIncluded(candidate, pinned, excluded))
    .map((candidate) => candidate.fact_id);
