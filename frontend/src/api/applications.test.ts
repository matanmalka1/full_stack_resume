import { afterEach, describe, expect, it, vi } from "vitest";

import {
  acknowledgementApplies,
  applicationDetailQueryOptions,
  duplicateMatchesFromProblem,
  startAnalysis,
  startDraftGeneration,
} from "./applications";
import { OPERATION_POLL_INTERVAL_MS } from "./operations";
import { ApiProblem, type ProblemDetails } from "./client";
import type { ApplicationDetail, ApplicationIntake, Operation } from "./contracts";

const intake = (overrides: Partial<ApplicationIntake> = {}): ApplicationIntake => ({
  company: "Acme",
  target_role: "Backend Engineer",
  job_text: "Job description text",
  source_url: null,
  ...overrides,
});

const problem = (overrides: Partial<ProblemDetails> = {}): ApiProblem =>
  new ApiProblem({
    type: "about:blank#duplicate_acknowledgement_required",
    title: "Precondition Failed",
    status: 412,
    code: "DUPLICATE_ACKNOWLEDGEMENT_REQUIRED",
    detail: "possible duplicate applications require explicit acknowledgement",
    ...overrides,
  });

const match = (matchedOn: string[] = ["company_title"]) => ({
  application_id: "app-existing",
  company: "Acme",
  target_role: "Backend Engineer",
  matched_on: matchedOn,
});

describe("acknowledgementApplies", () => {
  it("refuses an acknowledgement that answers nothing", () => {
    expect(acknowledgementApplies(undefined, intake())).toBe(false);
  });

  it("accepts an acknowledgement given for the same intake", () => {
    expect(acknowledgementApplies(intake(), intake())).toBe(true);
  });

  it("refuses an acknowledgement once any part of the intake moved", () => {
    expect(acknowledgementApplies(intake(), intake({ job_text: "Another posting" }))).toBe(false);
    expect(acknowledgementApplies(intake(), intake({ company: "Acme Ltd" }))).toBe(false);
    expect(acknowledgementApplies(intake(), intake({ target_role: "Data Engineer" }))).toBe(false);
    expect(
      acknowledgementApplies(intake(), intake({ source_url: "https://example.com/jobs/1" })),
    ).toBe(false);
  });
});

describe("duplicateMatchesFromProblem", () => {
  it("ignores anything that is not the duplicate refusal", () => {
    expect(duplicateMatchesFromProblem(new Error("network"))).toBeNull();
    expect(duplicateMatchesFromProblem(problem({ code: "PRECONDITION_FAILED" }))).toBeNull();
  });

  it("reads the candidates the create command named", () => {
    const matches = duplicateMatchesFromProblem(problem({ context: { matches: [match()] } }));

    expect(matches).toEqual([match()]);
  });

  /* An empty list still has to reach the screen: the server refused for duplicates and
     the explicit create-anyway path is the only way forward, named candidates or not. */
  it("reports a refusal that named no candidates as empty rather than absent", () => {
    expect(duplicateMatchesFromProblem(problem())).toEqual([]);
    expect(duplicateMatchesFromProblem(problem({ context: { matches: "none" } }))).toEqual([]);
  });

  it("drops a candidate carrying a detection reason the union does not know", () => {
    const context = { matches: [match(["company_title"]), match(["telepathy"])] };

    expect(duplicateMatchesFromProblem(problem({ context }))).toEqual([match(["company_title"])]);
  });
});

const operation = (overrides: Partial<Operation> = {}): Operation => ({
  id: "op-1",
  application_id: "app-1",
  operation_type: "analyze_job",
  status: "queued",
  is_terminal: false,
  phase: "queued",
  message: "",
  created_at: "2026-08-24T07:00:00Z",
  outputs: [],
  available_actions: ["cancel"],
  ...overrides,
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("startAnalysis", () => {
  it("names the snapshot and the idempotency key, and returns the queued Operation's route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(operation()), {
        status: 202,
        headers: {
          "Content-Type": "application/json",
          Location: "/api/v1/operations/op-1",
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const queued = await startAnalysis("app 1", "snap-1", "key-1");

    expect(queued.operationPath).toBe("/operations/op-1");
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/applications/app%201/analyses");
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      job_snapshot_id: "snap-1",
    });
    expect((fetchMock.mock.calls[0]?.[1]?.headers as Headers).get("Idempotency-Key")).toBe(
      "key-1",
    );
  });

  it("sends the configured AI provider only for a manual AI-mode command", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(operation()), {
        status: 202,
        headers: { "Content-Type": "application/json", Location: "/api/v1/operations/op-1" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await startAnalysis("app-1", "snap-1", "key-1", "openai");

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      job_snapshot_id: "snap-1",
      provider: "openai",
    });
  });

  /* §13 answers `202` and a `Location` naming the queued Operation. Anything else is not
     an Operation this client may follow, so it is refused rather than navigated to. */
  it("refuses an accepted body that does not name its queued Operation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify(operation()), {
          status: 202,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(startAnalysis("app-1", "snap-1", "key-1")).rejects.toThrow(
      "Accepted response did not identify its queued Operation",
    );
  });
});

/* §21: the no-review continuation. The `202`/`Location` obligation is `queuedOperation`'s
   and is covered once above; what is this command's own is that both sources travel
   explicitly. */
describe("startDraftGeneration", () => {
  it("names the exact analysis and selection plan rather than letting the server resolve them", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(operation({ operation_type: "create_draft" })), {
        status: 202,
        headers: {
          "Content-Type": "application/json",
          Location: "/api/v1/operations/op-1",
        },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const queued = await startDraftGeneration("app 1", "analysis-1", "plan-1", "key-2");

    expect(queued.operationPath).toBe("/operations/op-1");
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/applications/app%201/working-draft/generate",
    );
    /* `provider` is absent on purpose: `deterministic` is the server's default, and the
       deterministic path has to stay reachable with no key configured. */
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      job_analysis_id: "analysis-1",
      selection_plan_id: "plan-1",
    });
    expect((fetchMock.mock.calls[0]?.[1]?.headers as Headers).get("Idempotency-Key")).toBe(
      "key-2",
    );
  });

  it("names an approved parent and AI provider only when the caller explicitly supplies them", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(operation({ operation_type: "create_draft" })), {
        status: 202,
        headers: { "Content-Type": "application/json", Location: "/api/v1/operations/op-1" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await startDraftGeneration("app-1", "analysis-1", "plan-1", "key-2", {
      parentRevisionId: "revision-1",
      provider: "openai",
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      job_analysis_id: "analysis-1",
      selection_plan_id: "plan-1",
      parent_revision_id: "revision-1",
      provider: "openai",
    });
  });
});

/* The interval is a function of query state, so it is exercised as one: a stub carrying
   only the field it reads, rather than a live QueryClient. */
type RefetchInterval = Extract<
  ReturnType<typeof applicationDetailQueryOptions>["refetchInterval"],
  (...args: never[]) => unknown
>;

const interval = (data?: ApplicationDetail) => {
  const refetchInterval = applicationDetailQueryOptions("app-1").refetchInterval as RefetchInterval;
  const query = { state: { data, error: null } };
  return refetchInterval(query as unknown as Parameters<RefetchInterval>[0]);
};

describe("the application projection poll", () => {
  const projection = (active?: Operation) =>
    ({ active_operation: active }) as unknown as ApplicationDetail;

  it("follows an Operation the projection reports as live", () => {
    expect(interval(projection(operation()))).toBe(OPERATION_POLL_INTERVAL_MS);
  });

  it("stops once that Operation is terminal, trusting the backend rather than the status", () => {
    expect(interval(projection(operation({ status: "succeeded", is_terminal: true })))).toBe(false);
  });

  it("never starts polling a projection with no Operation on it", () => {
    expect(interval(projection())).toBe(false);
    expect(interval()).toBe(false);
  });
});
