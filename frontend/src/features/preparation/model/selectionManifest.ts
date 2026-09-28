import type { Requirement } from "@/api/analyses";
import type { SelectionPlanCandidate } from "@/api/contracts";
import { candidateIncluded, candidateLocked } from "./factGroups";

/* The engine's own accounting of one fact, read from the plan's frozen manifest.

   The selection ranks every candidate by a fixed tuple - requirement tier, then semantic
   score (profile + emphasis weight), then keyword hits, then pool position - and records
   the parts of that tuple on the plan. The API carries the manifest as an opaque object,
   so it is read narrowly here, the same way the analysis document is: a field that is
   missing or malformed is absent rather than guessed, and a manifest from an older policy
   simply explains less. */
export interface FactRanking {
  emphasisScore: number;
  gapSubstitute: boolean;
  keywordHits: number;
  profileScore: number;
  /* 2 where the fact is evidence for a mandatory requirement, 1 for a preferred one. */
  requirementRank: number;
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null;

const count = (value: unknown): number => (typeof value === "number" && Number.isFinite(value) ? value : 0);

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

/* Who decided a fact's place in the CV. "engine" means the ranking alone; "pinned" and
   "excluded" mean an explicit overlay on it - the reader's own marks, or an AI proposal,
   which the server stores in exactly the same two lists. */
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

/* The ranking, in words a reader can check against the posting. Each signal is one term
   of the engine's sort key, so the list is the actual reason a fact ranked where it did
   rather than a paraphrase of the outcome. */
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

/* One fact's move between two selections of the same Application. */
export interface SelectionChange {
  candidate: SelectionPlanCandidate;
  direction: "added" | "removed";
}

/* What a new plan changed against the set of facts the reader saw before it: the facts
   now on their way into the CV that were not, and the reverse. Only facts both plans
   know are compared as moves; a fact only the new plan carries counts as added when it
   is included. */
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
