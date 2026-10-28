import type { ApplicationDetail, Fact, FactDraftReason, GapQuestion, GapQuestionSet } from "@/api/contracts";

/* How the gap questions of §13a read on the analysis step: whether they can be asked,
   and what each question's card has to say. The server owns every outcome - which
   requirements get a question, whether an answer became a fact - so this module only
   reduces the records it returns to what one card shows. */

export const GAP_ANSWER_MAX_LENGTH = 2000;

/* Offered by the projection (§9), or offered but held while a question set is being
   written. Either way the step has questions to show or to ask; neither means none. */
export const gapQuestionsOffered = (detail: ApplicationDetail): boolean =>
  detail.available_actions.includes("ask_gap_questions") ||
  detail.blocked_actions.some((blocked) => blocked.action === "ask_gap_questions");

export const gapQuestionsAskable = (detail: ApplicationDetail): boolean =>
  detail.available_actions.includes("ask_gap_questions") && detail.latest_analysis_id != null;

/* The ask command in flight, from the projection: the set does not exist until it
   succeeds, so the step reports the run itself until then. */
export const askingOperationId = (detail: ApplicationDetail): string | null =>
  detail.active_operation?.operation_type === "ask_gap_questions" ? detail.active_operation.id : null;

export const importanceLabels: Record<GapQuestion["importance"], string> = {
  mandatory: "חובה",
  preferred: "מועדפת",
  unknown: "חשיבות לא מוצהרת",
};

/* A draft the engine refused, as the card names it: the numbers and terms the wording
   added are what the reader needs to see, so they travel apart from the sentence. */
export interface GapDraftFailure {
  unsupported: string[];
  /* Only a draft refused for wording carries the list; any other failure (the provider,
     a timeout) is reported by its code alone. */
  wording: boolean;
}

const isFactDraftReason = (reason: unknown): reason is FactDraftReason =>
  typeof reason === "object" && reason !== null && (reason as { code?: unknown }).code === "fact_draft";

export type GapQuestionView =
  | { kind: "open"; failure: GapDraftFailure | null }
  | { kind: "drafting" }
  | { kind: "answered"; answer: string; fact: Fact | null }
  | { kind: "skipped" };

/* One card per question, by its state. An open question whose newest draft ended without
   a fact is still open - the engine wrote nothing (§13a) - and is answered again, so the
   card keeps the form and says why the last answer did not become a fact. */
export const gapQuestionView = (question: GapQuestion): GapQuestionView => {
  switch (question.state) {
    case "drafting":
      return { kind: "drafting" };
    case "answered":
      return { kind: "answered", answer: question.answer ?? "", fact: question.fact ?? null };
    case "skipped":
      return { kind: "skipped" };
    case "open": {
      const draft = question.draft_operation ?? null;
      if (draft === null || !draft.is_terminal || draft.status === "succeeded") return { kind: "open", failure: null };
      const reason = draft.failure_reason;
      return {
        kind: "open",
        failure: isFactDraftReason(reason)
          ? { unsupported: reason.unsupported ?? [], wording: true }
          : { unsupported: [], wording: false },
      };
    }
  }
};

/* The wording the CV would carry, in the analysis language when the fact has it. */
export const gapFactRendering = (fact: Fact, language: GapQuestionSet["language"]): string =>
  (language === "he" ? fact.renderings.he : undefined) ?? fact.renderings.en ?? fact.meaning;

/* Counts for the section's heading line: how many questions still wait on the reader. */
export const openQuestionCount = (set: GapQuestionSet): number =>
  set.questions.filter((question) => question.state === "open" || question.state === "drafting").length;
