import type { components, operations, paths } from "../../../openapi/types";

export type ApiPaths = paths;
export type ApiOperations = operations;
export type ApiSchemas = components["schemas"];

export type ApplicationDetail = ApiSchemas["ApplicationDetailResponse"];
export type Operation = ApiSchemas["OperationResponse"];
export type WorkingDraft = ApiSchemas["WorkingDraftResponse"];
