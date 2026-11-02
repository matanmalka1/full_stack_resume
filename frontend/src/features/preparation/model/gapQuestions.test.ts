import { describe, expect, it } from "vitest";

import type { Fact, GapQuestion, Operation } from "@/api/contracts";
import { hasDraftInFlight } from "@/api/gapQuestions";
import { detail, operation } from "@/test/records";
import {
  askingOperationId,
  gapFactRendering,
  gapQuestionView,
  gapQuestionsAskable,
  gapQuestionsOffered,
  openQuestionCount,
} from "./gapQuestions";

const question = (overrides: Partial<GapQuestion> = {}): GapQuestion => ({
  id: "q-1",
  ordinal: 0,
  requirement_id: "requirement-1",
  requirement_text: "Experience selling AWS-based solutions",
  importance: "mandatory",
  coverage: "unsupported",
  question: "Have you sold cloud solutions?",
  state: "open",
  answer: null,
  fact: null,
  draft_operation: null,
  ...overrides,
});

const fact = (overrides: Partial<Fact> = {}): Fact => ({
  fact_id: "fact-1",
  meaning: "Sold cloud deals",
  provenance: "gap answer",
  renderings: { en: "Sold cloud deals", he: "מכר עסקאות ענן" },
  resume_style: "bullet",
  source: "situational_skills.json",
  status: "pending",
  tags: ["sales"],
  ...overrides,
});

const draft = (overrides: Partial<Operation>): Operation => ({
  ...operation(),
  id: "op-draft",
  operation_type: "draft_gap_fact",
  ...overrides,
});

describe("gap question availability", () => {
  it("is offered while the action is available or held by a running ask", () => {
    expect(gapQuestionsOffered(detail({ available_actions: ["ask_gap_questions"] }))).toBe(true);
    expect(
      gapQuestionsOffered(
        detail({
          available_actions: [],
          blocked_actions: [{ action: "ask_gap_questions", reasons: ["GAP_QUESTIONS_IN_PROGRESS"] }],
        }),
      ),
    ).toBe(true);
    expect(gapQuestionsOffered(detail({ available_actions: ["analyze"] }))).toBe(false);
  });

  it("can be asked only when available and an analysis exists", () => {
    expect(gapQuestionsAskable(detail({ available_actions: ["ask_gap_questions"], latest_analysis_id: "a-1" }))).toBe(
      true,
    );
    expect(gapQuestionsAskable(detail({ available_actions: ["ask_gap_questions"], latest_analysis_id: null }))).toBe(
      false,
    );
  });

  it("follows only an ask in flight", () => {
    expect(
      askingOperationId(
        detail({ active_operation: { ...operation(), id: "op-ask", operation_type: "ask_gap_questions" } }),
      ),
    ).toBe("op-ask");
    expect(askingOperationId(detail({ active_operation: operation() }))).toBeNull();
  });
});

describe("gapQuestionView", () => {
  it("keeps an unanswered question open with no failure", () => {
    expect(gapQuestionView(question())).toEqual({ kind: "open", failure: null });
  });

  it("names the terms a refused draft added and keeps the question open", () => {
    const refused = draft({
      status: "failed",
      is_terminal: true,
      failure_code: "INVALID_OUTPUT",
      failure_reason: { code: "fact_draft", problems: ["unsupported-term"], unsupported: ["AWS", "40%"] },
    });
    expect(gapQuestionView(question({ draft_operation: refused }))).toEqual({
      kind: "open",
      failure: { unsupported: ["AWS", "40%"], wording: true },
    });
  });

  it("reports a draft that failed for another reason without a term list", () => {
    const failed = draft({ status: "failed", is_terminal: true, failure_code: "PROVIDER_TIMEOUT" });
    expect(gapQuestionView(question({ draft_operation: failed }))).toEqual({
      kind: "open",
      failure: { unsupported: [], wording: false },
    });
  });

  it("maps drafting, answered and skipped", () => {
    expect(gapQuestionView(question({ state: "drafting" }))).toEqual({ kind: "drafting" });
    expect(gapQuestionView(question({ state: "skipped" }))).toEqual({ kind: "skipped" });
    expect(gapQuestionView(question({ state: "answered", answer: "Yes", fact: fact() }))).toEqual({
      kind: "answered",
      answer: "Yes",
      fact: fact(),
    });
  });
});

describe("question set helpers", () => {
  it("shows the analysis-language rendering, falling back to English", () => {
    expect(gapFactRendering(fact(), "he")).toBe("מכר עסקאות ענן");
    expect(gapFactRendering(fact(), "en")).toBe("Sold cloud deals");
    expect(gapFactRendering(fact({ renderings: { en: "Only English" } }), "he")).toBe("Only English");
  });

  it("counts open questions and polls only while a draft runs", () => {
    const set = {
      application_id: "app-1",
      questions: [question(), question({ id: "q-2", state: "drafting" }), question({ id: "q-3", state: "skipped" })],
    };
    expect(openQuestionCount(set)).toBe(2);
    expect(hasDraftInFlight(set)).toBe(true);
    expect(hasDraftInFlight({ ...set, questions: [question()] })).toBe(false);
    expect(hasDraftInFlight(undefined)).toBe(false);
  });
});
