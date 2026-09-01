import type { ReconciliationReport } from "./contracts";
import { apiRequest } from "./client";

export const reconcile = async (): Promise<ReconciliationReport> => {
  const response = await apiRequest<ReconciliationReport>("/api/v1/maintenance/reconciliations", {
    method: "POST",
  });
  return response.data;
};
