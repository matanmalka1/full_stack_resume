import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  applicationDetailQueryOptions,
  applicationDetailQueryPrefix,
  applicationListQueryOptions,
  applicationListQueryPrefix,
} from "./applications";
import { factsQueryKey, factsQueryPrefix } from "./facts";
import { cancelOperation, operationQueryOptions, retryOperation } from "./operations";
import { decisionMarkdownQueryOptions } from "./revisions";
import { queryClient } from "../app/queryClient";

const jsonResponse = (body: unknown, status = 200, headers: Record<string, string> = {}): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("query cache policy", () => {
  it("keeps list, detail, and filtered fact keys under their invalidation prefixes", () => {
    expect(applicationListQueryOptions({ search: "platform" }).queryKey).toEqual([
      ...applicationListQueryPrefix,
      "search=platform",
    ]);
    expect(applicationDetailQueryOptions("application-1").queryKey).toEqual([
      ...applicationDetailQueryPrefix,
      "application-1",
    ]);
    expect(factsQueryKey("pending")).toEqual([...factsQueryPrefix, "pending"]);
  });

  it("uses one list key for equivalent requests and distinct keys for distinct filters", () => {
    const filtersFirst = applicationListQueryOptions({
      activity: "closed",
      search: "platform",
      sort: "company",
    }).queryKey;
    const searchFirst = applicationListQueryOptions({
      sort: "company",
      search: "platform",
      activity: "closed",
    }).queryKey;
    const differentFilter = applicationListQueryOptions({
      activity: "open",
      search: "platform",
      sort: "company",
    }).queryKey;

    expect(filtersFirst).toEqual(searchFirst);
    expect(differentFilter).not.toEqual(filtersFirst);
  });

  it("keys decision markdown by every request argument", () => {
    expect(decisionMarkdownQueryOptions("revision-1", "application-1").queryKey).toEqual([
      "decision-markdown",
      "revision-1",
      "application-1",
    ]);
  });

  it("retries reads once and never retries writes", () => {
    const defaults = queryClient.getDefaultOptions();

    expect(defaults.queries?.retry).toBe(1);
    expect(defaults.queries?.retryDelay).toBeUndefined();
    expect(defaults.mutations?.retry).toBe(false);
  });
});

describe("Operation requests", () => {
  it("does not immediately retry a permanently missing Operation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          type: "about:blank#operation-not-found",
          title: "Operation not found",
          status: 404,
          code: "OPERATION_NOT_FOUND",
          detail: "Operation not found",
        },
        404,
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({
      defaultOptions: { queries: { retry: 1, retryDelay: 0 } },
    });

    await expect(client.fetchQuery(operationQueryOptions("missing-operation"))).rejects.toThrow("Operation not found");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("encodes ids for reads, cancellation, retry, and Location validation", async () => {
    const operationId = "operation/with space";
    const encodedPath = "/api/v1/operations/operation%2Fwith%20space";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: operationId }))
      .mockResolvedValueOnce(jsonResponse({ id: operationId }))
      .mockResolvedValueOnce(jsonResponse({ id: operationId }, 202, { Location: encodedPath }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    await client.fetchQuery(operationQueryOptions(operationId));
    await cancelOperation(operationId);
    await retryOperation(operationId, "retry-key");

    expect(fetchMock).toHaveBeenNthCalledWith(1, encodedPath, expect.objectContaining({ method: "GET" }));
    expect(fetchMock).toHaveBeenNthCalledWith(2, `${encodedPath}/cancel`, expect.objectContaining({ method: "POST" }));
    expect(fetchMock).toHaveBeenNthCalledWith(3, `${encodedPath}/retry`, expect.objectContaining({ method: "POST" }));
  });
});
