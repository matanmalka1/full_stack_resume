import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { Operation } from "@/api/contracts";
import { isTerminalOperation, operationQueryOptions } from "@/api/operations";

interface ProposalBaseline {
  fromPlanId: string | null;
  included: string[];
  operationId: string;
}

export type ProposalStatus =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "unknown" }
  | { kind: "failed"; operation: Operation }
  | { kind: "done"; resultPlanId: string | null };

// Kept in the query cache so it survives the panel unmounting while the proposal runs.
const baselineKey = (applicationId: string) => ["selection-proposal-baseline", applicationId] as const;

export const useSelectionProposal = (applicationId: string) => {
  const queryClient = useQueryClient();
  const baselineQuery = useQuery<ProposalBaseline | null>({
    queryKey: baselineKey(applicationId),
    queryFn: () => null,
    enabled: false,
    gcTime: Number.POSITIVE_INFINITY,
    staleTime: Number.POSITIVE_INFINITY,
  });
  const baseline = baselineQuery.data ?? null;
  const operationQuery = useQuery({
    ...operationQueryOptions(baseline?.operationId ?? ""),
    enabled: baseline !== null,
  });
  const operation = operationQuery.data;

  const status: ProposalStatus =
    baseline === null
      ? { kind: "idle" }
      : operation === undefined && operationQuery.error != null
        ? { kind: "unknown" }
        : operation === undefined || !isTerminalOperation(operation)
          ? { kind: "running" }
          : operation.status === "succeeded"
            ? {
                kind: "done",
                resultPlanId:
                  operation.outputs.find((output) => output.output_type === "selection_plan" && output.active)
                    ?.output_id ?? null,
              }
            : { kind: "failed", operation };

  return {
    baseline,
    dismiss: () => queryClient.setQueryData<ProposalBaseline | null>(baselineKey(applicationId), null),
    remember: (next: ProposalBaseline) =>
      queryClient.setQueryData<ProposalBaseline | null>(baselineKey(applicationId), next),
    status,
  };
};
