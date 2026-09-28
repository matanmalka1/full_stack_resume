import type { ApiSchemas } from "./contracts";

export type ProblemDetails = ApiSchemas["ProblemDetails"];

export class ApiProblem extends Error {
  readonly problem: ProblemDetails;

  constructor(problem: ProblemDetails) {
    super(problem.detail);
    this.name = "ApiProblem";
    this.problem = problem;
  }
}

export interface ApiRequestOptions {
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  etag?: string;
  idempotencyKey?: string;
  signal?: AbortSignal;
}

export type ApiPath = `/api/v1/${string}`;

export interface ApiResponse<T> {
  data: T;
  status: number;
  contentDisposition: string | null;
  etag: string | null;
  location: string | null;
}

const JSON_CONTENT_TYPE = "application/json";
const PROBLEM_CONTENT_TYPE = "application/problem+json";

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === "object" && value !== null;
};

const isProblemDetails = (value: unknown): value is ProblemDetails => {
  return (
    isRecord(value) &&
    typeof value.type === "string" &&
    typeof value.title === "string" &&
    typeof value.status === "number" &&
    typeof value.code === "string" &&
    typeof value.detail === "string"
  );
};

const readJson = async (response: Response): Promise<unknown> => {
  const contentType = response.headers.get("Content-Type") ?? "";
  if (!contentType.includes(JSON_CONTENT_TYPE) && !contentType.includes(PROBLEM_CONTENT_TYPE)) {
    return undefined;
  }
  return response.json();
};

const fallbackProblem = (response: Response): ProblemDetails => {
  return {
    type: "about:blank#unexpected-http-error",
    title: "Request failed",
    status: response.status,
    code: "UNEXPECTED_HTTP_ERROR",
    detail: `HTTP ${response.status} without a Problem Details body`,
  };
};

/* Problems this client raises itself. Like the server's, their title and detail are for
   the log; the reader's copy comes from the code (`ui/errorMessages.ts`). */
const clientProblem = (code: string, title: string, detail: string): ProblemDetails => ({
  type: `about:blank#${code.toLowerCase()}`,
  title,
  status: 0,
  code,
  detail,
});

const isAbortError = (error: unknown): boolean => error instanceof DOMException && error.name === "AbortError";

const invalidServerResponse = (): ApiProblem =>
  new ApiProblem(
    clientProblem("INVALID_SERVER_RESPONSE", "Invalid server response", "The response body could not be read as JSON."),
  );

export const apiRequest = async <T>(path: ApiPath, options: ApiRequestOptions = {}): Promise<ApiResponse<T>> => {
  const headers = new Headers({
    Accept: `${JSON_CONTENT_TYPE}, ${PROBLEM_CONTENT_TYPE}`,
  });

  if (options.body !== undefined) {
    headers.set("Content-Type", JSON_CONTENT_TYPE);
  }
  if (options.etag !== undefined) {
    headers.set("If-Match", options.etag);
  }
  if (options.idempotencyKey !== undefined) {
    headers.set("Idempotency-Key", options.idempotencyKey);
  }

  let response: Response;
  try {
    response = await fetch(path, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal,
    });
  } catch (error) {
    // TanStack Query uses AbortError as control flow when a query is cancelled.
    if (isAbortError(error)) throw error;
    throw new ApiProblem(
      clientProblem(
        "NETWORK_UNAVAILABLE",
        "Network unavailable",
        error instanceof Error ? error.message : "The request did not reach the server.",
      ),
    );
  }

  let payload: unknown;
  try {
    payload = await readJson(response);
  } catch {
    if (!response.ok) {
      throw new ApiProblem(fallbackProblem(response));
    }
    throw invalidServerResponse();
  }

  if (!response.ok) {
    throw new ApiProblem(isProblemDetails(payload) ? payload : fallbackProblem(response));
  }
  if (payload === undefined) {
    throw invalidServerResponse();
  }

  return {
    data: payload as T,
    status: response.status,
    contentDisposition: response.headers.get("Content-Disposition"),
    etag: response.headers.get("ETag"),
    location: response.headers.get("Location"),
  };
};
