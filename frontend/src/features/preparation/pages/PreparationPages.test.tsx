import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, Operation } from "@/api/contracts";
import { detail as baseDetail, json, renderRoute, settings } from "@/test/fixtures";
import { AnalysisPage } from "./AnalysisPage";
import { MatchingPage } from "./MatchingPage";
import { VerificationPage } from "./VerificationPage";

const APPLY_PATH = "/api/v1/analyses/analysis-1/apply-decisions";
const JOB_TEXT_HASH = "c".repeat(64);

const requirement = (id: string, text: string, importance: string, coverage: string, extra = {}) => ({
  requirement_id: id,
  text,
  importance,
  coverage,
  supporting_fact_ids: coverage === "matched" ? ["fact-1"] : [],
  boundary_fact_ids: [],
  ...extra,
});

/* An Application whose analysis is in force and whose draft is next. */
const analyzed = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  baseDetail({
    preparation_state: "ready_to_draft",
    content_check: "none",
    available_actions: ["create_draft", "analyze", "edit_matching_configuration"],
    recommended_action: "create_draft",
    latest_analysis: {
      id: "analysis-1",
      application_id: "app-1",
      job_text_hash: JOB_TEXT_HASH,
      version_number: 1,
      analysis: {
        analysis_version: "3.0",
        track: "development",
        profile: "development",
        emphasis: "development-backend",
        language: "he",
        summary: "A backend role.",
        keywords: [],
        requirements: [
          requirement("r1", "Python", "mandatory", "matched"),
          requirement("r2", "Team lead", "mandatory", "unsupported", {
            shortfall_severity: "material",
            shortfall_reason: "No fact shows leading a team.",
          }),
          requirement("r3", "Kubernetes", "preferred", "partial", { shortfall_severity: "minor" }),
        ],
        issues: [],
        source_coverage: 1,
        user_override: {},
      },
      fit_level: "medium",
      fit_score: 0.6,
      gaps: [],
      provider: "openai",
      model: "gpt-5.6-terra",
      created_at: "2026-08-24T07:00:00Z",
    },
    ...overrides,
  });

const stub = (routes: Record<string, () => Response>) => {
  const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
    const path = String(input);
    const answer =
      routes[path] ?? (path === "/api/v1/settings" ? () => json(settings({ provider_configured: true })) : undefined);
    return Promise.resolve(answer === undefined ? json({ title: "not stubbed" }, 404) : answer());
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AnalysisPage", () => {
  it("states the verdict, lists one importance at a time, and leads on to matching and the draft", async () => {
    stub({ "/api/v1/applications/app-1": () => json(analyzed()) });
    renderRoute("/applications/app-1/analysis", "/applications/:applicationId/analysis", <AnalysisPage />);

    expect(await screen.findByRole("heading", { name: "התאמה בינונית" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "ניתוח המשרה" })).toBeInTheDocument();

    const table = screen.getByRole("table", { name: "דרישות חובה" });
    expect(within(table).getByText("Python")).toBeInTheDocument();
    expect(within(table).getByText("פער מהותי")).toBeInTheDocument();
    expect(within(table).queryByText("Kubernetes")).not.toBeInTheDocument();
    /* What limits coverage is explained beside the table, for the rows on view. */
    expect(screen.getByText("No fact shows leading a team.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "דרישות מועדפות" }));
    expect(within(screen.getByRole("table", { name: "דרישות מועדפות" })).getByText("Kubernetes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "דרישות מועדפות" })).toHaveAttribute("aria-pressed", "true");

    expect(screen.getByRole("link", { name: "הגדרות ההתאמה" })).toHaveAttribute(
      "href",
      "/applications/app-1/analysis/matching",
    );
    expect(screen.getByRole("link", { name: "המשך לטיוטה" })).toHaveAttribute(
      "href",
      "/applications/app-1/verification",
    );
    expect(screen.getByRole("link", { name: "חזרה לפרטי המועמדות" })).toHaveAttribute("href", "/applications/app-1");
  });

  it("offers the analysis itself before there is one", async () => {
    stub({
      "/api/v1/applications/app-1": () =>
        json(
          baseDetail({
            preparation_state: "needs_analysis",
            latest_analysis_id: null,
            document_id: null,
            document_hash: null,
            available_actions: ["analyze"],
            recommended_action: "analyze",
          }),
        ),
    });
    renderRoute("/applications/app-1/analysis", "/applications/:applicationId/analysis", <AnalysisPage />);

    expect(await screen.findByRole("heading", { name: "המשרה טרם נותחה" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "ניתוח המשרה" })).toBeEnabled();
    expect(screen.queryByRole("link", { name: "המשך לטיוטה" })).not.toBeInTheDocument();
  });

  it("is the run's own screen while the analysis runs", async () => {
    const running: Operation = {
      id: "op-1",
      application_id: "app-1",
      operation_type: "analyze_job",
      status: "running",
      phase: "executing",
      is_terminal: false,
      available_actions: ["cancel"],
      outputs: [],
      message: "",
      created_at: "2026-08-24T07:00:00Z",
    };
    stub({
      "/api/v1/applications/app-1": () =>
        json(
          baseDetail({
            preparation_state: "needs_analysis",
            latest_analysis_id: null,
            document_id: null,
            document_hash: null,
            available_actions: [],
            recommended_action: null,
            active_operation: running,
          }),
        ),
      "/api/v1/operations/op-1": () => json(running),
    });
    renderRoute("/applications/app-1/analysis", "/applications/:applicationId/analysis", <AnalysisPage />);

    expect(await screen.findByRole("heading", { level: 1, name: "הרצת ניתוח המשרה" })).toBeInTheDocument();
    const steps = screen.getByRole("list", { name: "שלבי ההרצה" });
    expect(within(steps).getByText("ביצוע").closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("link", { name: "חזרה ללוח" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "ניתוח המשרה" })).not.toBeInTheDocument();
  });

  it("reports an analysis that ended without a result in the same place", async () => {
    const failed: Operation = {
      id: "op-1",
      application_id: "app-1",
      operation_type: "analyze_job",
      status: "failed",
      phase: "completed",
      is_terminal: true,
      available_actions: ["retry"],
      outputs: [],
      message: "",
      failure_code: "PROVIDER_NOT_CONFIGURED",
      created_at: "2026-08-24T07:00:00Z",
      started_at: "2026-08-24T07:00:01Z",
    };
    stub({
      "/api/v1/applications/app-1": () =>
        json(
          baseDetail({
            preparation_state: "needs_analysis",
            latest_analysis_id: null,
            document_id: null,
            document_hash: null,
            available_actions: ["analyze"],
            recommended_action: "analyze",
            latest_operation: failed,
          }),
        ),
      "/api/v1/operations/op-1": () => json(failed),
      "/api/v1/settings": () => json(settings({ provider_configured: false })),
    });
    renderRoute("/applications/app-1/analysis", "/applications/:applicationId/analysis", <AnalysisPage />);

    expect(await screen.findByRole("heading", { level: 1, name: "לא הוגדר ספק AI" })).toBeInTheDocument();
    expect(screen.getByText("הרצת ניתוח המשרה · הפעולה לא בוצעה")).toBeInTheDocument();
    /* With no provider a retry would fail the same way, so Settings is the way on. */
    expect(screen.getByRole("link", { name: "להגדרות" })).toHaveAttribute("href", "/settings");
    expect(screen.queryByRole("button", { name: "הרצה מחדש" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "חזרה למועמדות" })).toHaveAttribute("href", "/applications/app-1");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("MatchingPage", () => {
  it("saves only what changed against the analysis the form read, then returns to the analysis", async () => {
    let current = analyzed();
    const fetchMock = stub({
      "/api/v1/applications/app-1": () => json(current),
      [APPLY_PATH]: () => {
        current = analyzed({ latest_analysis_id: "analysis-2" });
        return json({ application_id: "app-1", analysis_id: "analysis-2", state: current });
      },
    });
    renderRoute("/applications/app-1/analysis/matching", "/applications/:applicationId/*", <MatchingPage />);

    const save = await screen.findByRole("button", { name: "שמירה" });
    expect(save).toBeDisabled();
    expect(screen.getByRole("link", { name: "ביטול" })).toHaveAttribute("href", "/applications/app-1/analysis");
    expect(screen.getByLabelText("מסלול")).toHaveValue("development");

    fireEvent.change(screen.getByLabelText("דגש"), { target: { value: "leadership" } });
    expect(save).toBeEnabled();
    fireEvent.click(save);

    await waitFor(() => expect(fetchMock.mock.calls.some((call) => call[0] === APPLY_PATH)).toBe(true));
    const body = JSON.parse(String(fetchMock.mock.calls.find((call) => call[0] === APPLY_PATH)?.[1]?.body)) as Record<
      string,
      unknown
    >;
    expect(body).toMatchObject({ expected_analysis_id: "analysis-1", emphasis_override: "leadership" });
    expect(body).not.toHaveProperty("track_override");
  });
});

describe("VerificationPage", () => {
  it("leads with the recommended action and lists the others beside the alerts", async () => {
    stub({
      "/api/v1/applications/app-1": () =>
        json(
          analyzed({
            available_actions: ["create_draft", "build_from_analysis"],
            latest_analysis_id: "analysis-2",
            warnings: [
              {
                code: "DOCUMENT_ON_OLDER_ANALYSIS",
                entity_references: {},
                message: "The document is on an older analysis.",
              },
            ],
          }),
        ),
    });
    renderRoute("/applications/app-1/verification", "/applications/:applicationId/verification", <VerificationPage />);

    const recommended = await screen.findByRole("heading", { name: "יצירת טיוטה" });
    expect(recommended.closest("section")).toHaveTextContent("הפעולה המומלצת");
    expect(await screen.findByRole("button", { name: "יצירת טיוטה" })).toBeEnabled();
    expect(screen.getByRole("heading", { name: "התראות" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "בנייה מחדש מהניתוח החדש" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "חזרה לניתוח המשרה" })).toHaveAttribute(
      "href",
      "/applications/app-1/analysis",
    );
  });
});
