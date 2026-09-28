import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { Operation } from "@/api/contracts";
import { isTerminalOperation, operationQueryOptions } from "@/api/operations";

/* The selection as it stood when an AI proposal was requested, so the proposal's result
   can be reported as what it changed rather than as a new list the reader must compare
   by memory.

   Held in the query cache rather than component state: while the proposal runs the
   workflow may withdraw the selection panel altogether (its command is blocked behind the
   live Operation), and state inside it would be gone by the time the result lands. The
   cache outlives that unmount for the session, which is exactly as long as "what did the
   last proposal change" is a question worth answering. */
interface ProposalBaseline {
  fromPlanId: string | null;
  included: string[];
  operationId: string;
}

export type ProposalStatus =
  | { kind: "idle" }
  | { kind: "running" }
  /* The Operation could no longer be read; the plan on screen is still the truth. */
  | { kind: "unknown" }
  | { kind: "failed"; operation: Operation }
  | { kind: "done"; resultPlanId: string | null };

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
