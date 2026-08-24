export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  code: string;
  detail: string;
  context?: Record<string, unknown>;
  instance?: string;
}

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
    detail: "הבקשה נכשלה. ניתן לנסות שוב או לבדוק את פרטי השגיאה הבטוחים.",
  };
};

export const apiRequest = async <T>(
  path: ApiPath,
  options: ApiRequestOptions = {},
): Promise<ApiResponse<T>> => {
  const headers = new Headers({ Accept: JSON_CONTENT_TYPE });

  if (options.body !== undefined) {
    headers.set("Content-Type", JSON_CONTENT_TYPE);
  }
  if (options.etag !== undefined) {
    headers.set("If-Match", options.etag);
  }
  if (options.idempotencyKey !== undefined) {
    headers.set("Idempotency-Key", options.idempotencyKey);
  }

  const response = await fetch(path, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });
  const payload = await readJson(response);

  if (!response.ok) {
    throw new ApiProblem(isProblemDetails(payload) ? payload : fallbackProblem(response));
  }

  return {
    data: payload as T,
    status: response.status,
    etag: response.headers.get("ETag"),
    location: response.headers.get("Location"),
  };
};
