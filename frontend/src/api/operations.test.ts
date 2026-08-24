import { describe, expect, it } from "vitest";

import { ApiProblem } from "./client";
import type { Operation } from "./contracts";
import {
  OPERATION_POLL_INTERVAL_MS,
  isPermanentFailure,
  isTerminalOperation,
  operationQueryOptions,
} from "./operations";

const operation = (overrides: Partial<Operation> = {}): Operation => ({
  id: "op-1",
  application_id: "app-1",
  operation_type: "analyze_job",
  status: "running",
  is_terminal: false,
  phase: "executing",
  message: "",
  created_at: "2026-08-24T07:00:00Z",
  outputs: [],
  ...overrides,
});

const problem = (status: number, code: string): ApiProblem =>
  new ApiProblem({
    type: "about:blank",
    title: "Request failed",
    status,
    code,
    detail: "detail",
  });

/* The interval is a function of query state, so it is exercised as one: a stub carrying
   only the two fields it reads, rather than a live QueryClient. The callback type is
   taken from the options object instead of being restated, so the return type stays
   checked and only the stub argument is asserted. */
type RefetchInterval = Extract<
  ReturnType<typeof operationQueryOptions>["refetchInterval"],
  (...args: never[]) => unknown
>;

const interval = (state: { data?: Operation; error?: unknown }) => {
  const refetchInterval = operationQueryOptions("op-1").refetchInterval as RefetchInterval;
  const query = { state: { data: state.data, error: state.error ?? null } };
  return refetchInterval(query as unknown as Parameters<RefetchInterval>[0]);
};

describe("isTerminalOperation", () => {
  it("trusts the backend rather than re-deriving the status", () => {
    expect(isTerminalOperation(operation({ status: "succeeded", is_terminal: true }))).toBe(true);
    expect(isTerminalOperation(operation({ status: "running", is_terminal: false }))).toBe(false);
  });

  it("treats a missing Operation as not terminal", () => {
    expect(isTerminalOperation(undefined)).toBe(false);
  });
});

describe("isPermanentFailure", () => {
  it("stops on a 4xx that cannot change", () => {
    expect(isPermanentFailure(problem(404, "UNKNOWN_RECORD"))).toBe(true);
    expect(isPermanentFailure(problem(422, "VALIDATION_ERROR"))).toBe(true);
  });

  it("keeps 408 and 429, which say later rather than never", () => {
    expect(isPermanentFailure(problem(408, "REQUEST_TIMEOUT"))).toBe(false);
    expect(isPermanentFailure(problem(429, "RATE_LIMITED"))).toBe(false);
  });

  it("keeps a 5xx and a transport error", () => {
    expect(isPermanentFailure(problem(503, "UNAVAILABLE"))).toBe(false);
    expect(isPermanentFailure(new TypeError("Failed to fetch"))).toBe(false);
    expect(isPermanentFailure(null)).toBe(false);
  });
});

describe("the poll interval", () => {
  it("keeps polling while the Operation is live", () => {
    expect(interval({ data: operation() })).toBe(OPERATION_POLL_INTERVAL_MS);
  });

  it("keeps polling before the first response arrives", () => {
    expect(interval({})).toBe(OPERATION_POLL_INTERVAL_MS);
  });

  it("stops once the Operation is terminal", () => {
    expect(interval({ data: operation({ status: "failed", is_terminal: true }) })).toBe(false);
  });

  it("stops on a permanent failure instead of looping forever", () => {
    expect(interval({ error: problem(404, "UNKNOWN_RECORD") })).toBe(false);
  });

  it("survives a transient failure", () => {
    expect(interval({ error: problem(503, "UNAVAILABLE") })).toBe(OPERATION_POLL_INTERVAL_MS);
    expect(interval({ error: new TypeError("Failed to fetch") })).toBe(
      OPERATION_POLL_INTERVAL_MS,
    );
  });
});
