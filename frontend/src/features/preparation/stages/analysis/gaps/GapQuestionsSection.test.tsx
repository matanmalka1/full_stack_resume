import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { GapQuestion, GapQuestionSet } from "@/api/contracts";
import { detail, json, operation } from "@/test/fixtures";
import { GapQuestionsSection } from "./GapQuestionsSection";

const question = (id: string, overrides: Partial<GapQuestion> = {}): GapQuestion => ({
  id,
  ordinal: 0,
  requirement_id: `requirement-${id}`,
  requirement_text: `Requirement ${id}`,
  importance: "mandatory",
  coverage: "unsupported",
  question: `Question ${id}?`,
  state: "open",
  answer: null,
  fact: null,
  draft_operation: null,
  ...overrides,
});

const questionSet = (questions: GapQuestion[]): GapQuestionSet => ({
  application_id: "app-1",
  job_analysis_id: "analysis-1",
  operation_id: questions.length === 0 ? null : "op-ask",
  language: "en",
  asked_at: questions.length === 0 ? null : "2026-10-28T00:00:00Z",
  questions,
});

const offeredDetail = detail({ available_actions: ["ask_gap_questions"], latest_analysis_id: "analysis-1" });

const stub = (set: GapQuestionSet) => {
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/gap-questions") && (init?.method ?? "GET") === "GET") return Promise.resolve(json(set));
    if (url.endsWith("/gap-questions") && init?.method === "POST") {
      const queued = { ...operation(), id: "op-ask", operation_type: "ask_gap_questions" };
      return Promise.resolve(json(queued, 202, { Location: "/api/v1/operations/op-ask" }));
    }
    if (url.endsWith("/answer")) {
      const queued = { ...operation(), id: "op-draft", operation_type: "draft_gap_fact" };
      return Promise.resolve(json(queued, 202, { Location: "/api/v1/operations/op-draft" }));
    }
    if (url.includes("/operations/")) return Promise.resolve(json(operation()));
    return Promise.resolve(json({ status: 404, code: "ROUTE_NOT_FOUND" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

const renderSection = (value = offeredDetail) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchInterval: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <GapQuestionsSection detail={value} profile={null} />
    </QueryClientProvider>,
  );
};

afterEach(() => vi.unstubAllGlobals());

describe("GapQuestionsSection", () => {
  it("renders nothing and reads nothing when the action is not offered", () => {
    const fetchMock = stub(questionSet([]));
    renderSection(detail({ available_actions: ["analyze"] }));
    expect(screen.queryByRole("heading", { name: "השלמת פערים בעובדות" })).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("asks for questions about the newest analysis", async () => {
    const fetchMock = stub(questionSet([]));
    renderSection();
    fireEvent.click(await screen.findByRole("button", { name: "שאלות על פערים" }));
    const isPost = ([, request]: Parameters<typeof fetch>) => request?.method === "POST";
    await waitFor(() => expect(fetchMock.mock.calls.some(isPost)).toBe(true));
    const [, sent] = fetchMock.mock.calls.find(isPost)!;
    expect(JSON.parse(String(sent?.body))).toEqual({ job_analysis_id: "analysis-1" });
    expect(screen.getByText(/תיחשב רק אחרי שתאושר/)).toBeInTheDocument();
  });

  it("shows every question state", async () => {
    stub(
      questionSet([
        question("open"),
        question("drafting", { state: "drafting", answer: null }),
        question("answered", {
          state: "answered",
          answer: "I sold cloud deals",
          fact: {
            fact_id: "fact-1",
            meaning: "Sold cloud deals",
            provenance: "answer",
            renderings: { en: "Sold cloud deals to enterprise buyers" },
            resume_style: "bullet",
            source: "situational_skills.json",
            status: "pending",
            tags: ["sales"],
          },
        }),
        question("skipped", { state: "skipped" }),
        question("failed", {
          draft_operation: {
            ...operation(),
            id: "op-failed",
            operation_type: "draft_gap_fact",
            status: "failed",
            is_terminal: true,
            failure_code: "INVALID_OUTPUT",
            failure_reason: { code: "fact_draft", problems: ["unsupported-number"], unsupported: ["40%"] },
          },
        }),
      ]),
    );
    renderSection();

    const card = async (id: string) => within(await screen.findByRole("article", { name: `Question ${id}?` }));

    const open = await card("open");
    expect(open.getByText("Requirement open")).toBeInTheDocument();
    expect(open.getByRole("textbox", { name: "התשובה שלך" })).toBeInTheDocument();
    expect(open.getByRole("button", { name: "שליחה" })).toBeDisabled();
    expect(open.getByRole("button", { name: "דילוג" })).toBeEnabled();

    expect((await card("drafting")).getByText("מנסחים עובדה מהתשובה שלך…")).toBeInTheDocument();

    const answered = await card("answered");
    expect(answered.getByText("I sold cloud deals")).toBeInTheDocument();
    expect(answered.getByText("Sold cloud deals to enterprise buyers")).toBeInTheDocument();
    expect(answered.getByText("ממתינה לאישור")).toBeInTheDocument();
    expect(answered.getByRole("button", { name: "עריכה" })).toBeInTheDocument();
    expect(answered.getByRole("button", { name: "אישור העובדה" })).toBeDisabled();
    expect(answered.getByText(/יש לאשר אותה ולהריץ את הניתוח מחדש/)).toBeInTheDocument();

    expect((await card("skipped")).getByText("דילגת על השאלה הזו.")).toBeInTheDocument();

    const failed = await card("failed");
    expect(failed.getByText("התשובה לא הפכה לעובדה")).toBeInTheDocument();
    expect(failed.getByText("40%")).toBeInTheDocument();
    expect(failed.getByRole("textbox", { name: "התשובה שלך" })).toBeInTheDocument();

    expect(screen.getByText("3 מתוך 5 שאלות ממתינות לתשובה.")).toBeInTheDocument();
  });

  it("sends the trimmed answer as a draft command", async () => {
    const fetchMock = stub(questionSet([question("open")]));
    renderSection();
    const open = within(await screen.findByRole("article", { name: "Question open?" }));
    fireEvent.change(open.getByRole("textbox", { name: "התשובה שלך" }), { target: { value: "  Sold deals  " } });
    fireEvent.click(open.getByRole("button", { name: "שליחה" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/answer"))).toBe(true));
    const [, init] = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/answer"))!;
    expect(JSON.parse(String(init?.body))).toEqual({ answer: "Sold deals" });
  });
});
