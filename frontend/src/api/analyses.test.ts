import { afterEach, describe, expect, it, vi } from "vitest";

import { applyAnalysisDecisions, classificationFromAnalysis } from "./analyses";
import type { ApplicationDetail } from "./contracts";

const APPLY_PATH = "/api/v1/analyses/analysis%201/apply-decisions";

const jsonResponse = (body: unknown, status = 201): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const decided = {
  application_id: "app-1",
  job_analysis_id: "analysis-2",
  selection_plan_id: "plan-2",
  created_analysis: true,
  analysis: {},
  plan: {},
};

const analysis = (overrides: Record<string, unknown> = {}) => ({
  track: "sales",
  profile: "account-manager",
  emphasis: "account-growth",
  language: "he",
  fit: "low",
  gaps: [
    { requirement: "5 years of Kubernetes", severity: "hard", reason: "missing" },
    { requirement: "German", severity: "warning", reason: "missing" },
  ],
  user_override: { profile: "account-manager" },
  rationale: "The posting is an account-growth role.",
  confidence: 0.82,
  keywords: ["CRM", "renewals"],
  mandatory_requirements: ["5 years of Kubernetes"],
  preferred_requirements: ["German"],
  ...overrides,
});

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  ({
    active_analysis_id: "analysis-1",
    latest_analysis: {
      id: "analysis-1",
      application_id: "app-1",
      job_snapshot_id: "snap-1",
      version_number: 1,
      analysis: analysis(),
      provider: "deterministic",
      model: "rules-v1",
      created_at: "2026-08-24T07:00:00Z",
    },
    ...overrides,
  }) as ApplicationDetail;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("applyAnalysisDecisions", () => {
  it("commits every decision in one request to the named analysis", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(decided));
    vi.stubGlobal("fetch", fetchMock);

    await applyAnalysisDecisions("analysis 1", "app-1", {
      track_override: "sales",
      profile_override: "account-manager",
      emphasis_override: "account-growth",
      language_override: "he",
      accept_low_fit: true,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [path, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(path).toBe(APPLY_PATH);
    expect(init.method).toBe("POST");
    /* §13 is synchronous and commits nothing durable to poll, so there is no
       `Idempotency-Key` obligation to carry. */
    expect(new Headers(init.headers).get("Idempotency-Key")).toBeNull();
    expect(JSON.parse(init.body as string)).toEqual({
      application_id: "app-1",
      accept_low_fit: true,
      track_override: "sales",
      profile_override: "account-manager",
      emphasis_override: "account-growth",
      language_override: "he",
    });
  });

  it("withholds a blank decision instead of sending it as an empty value", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(decided));
    vi.stubGlobal("fetch", fetchMock);

    await applyAnalysisDecisions("analysis 1", "app-1", {
      track_override: null,
      profile_override: "account-manager",
      emphasis_override: null,
      language_override: null,
      accept_low_fit: false,
    });

    /* Decisions accumulate server-side, so a withheld field must be absent: sending
       `""` would be a value that settles nothing, and the server filters it anyway. */
    expect(JSON.parse((fetchMock.mock.calls[0] as [string, RequestInit])[1].body as string)).toEqual(
      {
        application_id: "app-1",
        accept_low_fit: false,
        profile_override: "account-manager",
      },
    );
  });

  it("never sends the fact overlay this screen does not collect", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(decided));
    vi.stubGlobal("fetch", fetchMock);

    await applyAnalysisDecisions("analysis 1", "app-1", {
      track_override: "sales",
      profile_override: null,
      emphasis_override: null,
      language_override: null,
      accept_low_fit: false,
    });

    const body = JSON.parse((fetchMock.mock.calls[0] as [string, RequestInit])[1].body as string);
    expect(body).not.toHaveProperty("pinned_fact_ids");
    expect(body).not.toHaveProperty("excluded_fact_ids");
  });
});

describe("classificationFromAnalysis", () => {
  it("reads the classification and both gap severities from the active analysis", () => {
    expect(classificationFromAnalysis(detail())).toEqual({
      track: "sales",
      profile: "account-manager",
      emphasis: "account-growth",
      language: "he",
      fit: "low",
      gaps: [
        { requirement: "5 years of Kubernetes", severity: "hard", reason: "missing" },
        { requirement: "German", severity: "warning", reason: "missing" },
      ],
      decided: ["profile"],
      rationale: "The posting is an account-growth role.",
      confidence: 0.82,
      keywords: ["CRM", "renewals"],
      mandatoryRequirements: ["5 years of Kubernetes"],
      preferredRequirements: ["German"],
    });
  });

  it("reports a value it cannot recognize as absent rather than as undefined", () => {
    const read = classificationFromAnalysis(
      detail({
        latest_analysis: {
          ...detail().latest_analysis!,
          analysis: analysis({
            track: "quantum-sales",
            fit: "excellent",
            gaps: "not-a-list",
            rationale: 42,
            confidence: "high",
            keywords: ["CRM", 7],
          }),
        },
      }),
    );

    expect(read).not.toBeNull();
    expect(read?.track).toBeNull();
    expect(read?.fit).toBeNull();
    expect(read?.gaps).toEqual([]);
    expect(read?.rationale).toBeNull();
    /* A non-numeric confidence is absent rather than rendered as NaN%. */
    expect(read?.confidence).toBeNull();
    /* A mixed list keeps the strings and drops what is not one, rather than failing whole. */
    expect(read?.keywords).toEqual(["CRM"]);
    /* The values it *can* read are still read: one unknown does not blank the rest. */
    expect(read?.profile).toBe("account-manager");
  });

  it("refuses to show an analysis that is no longer the active one", () => {
    /* `latest_analysis` is the newest analysis of any snapshot; `active_analysis_id` is
       the newest for the active snapshot. After a new JobSnapshot they diverge, and the
       decision is sent to the active one - so showing the other would describe a
       different decision than the one being made. */
    expect(classificationFromAnalysis(detail({ active_analysis_id: "analysis-9" }))).toBeNull();
    expect(classificationFromAnalysis(detail({ active_analysis_id: null }))).toBeNull();
  });
});
