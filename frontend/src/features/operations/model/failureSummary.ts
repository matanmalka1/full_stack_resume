import type { Operation } from "@/api/contracts";
import {
  failurePresentations,
  failureReasonDetail,
  missingProviderPresentation,
  providerNowConfiguredPresentation,
  statusLabels,
  terminalSummaries,
  unknownFailureGuidance,
} from "./operationLabels";

export interface FailureSummary {
  /* The headline: the catalogue's title for the failure, or the status word. */
  title: string;
  /* What happened and what to do, from the catalogue - never the server's own text. */
  sentences: string[];
  /* No provider is usable, so a retry would fail the same way and Settings is the way on. */
  missingProvider: boolean;
}

/* The same reading of a run that ended without a result as the report's, for the phone's
   failure page: which catalogue entry speaks for it, whether a missing provider makes
   Settings the fix rather than a retry, and the reason's own detail where one is worded.
   A failure the catalogue has no entry for gets the safe general line. */
export const failureSummary = (
  operation: Operation,
  providerUsable: boolean,
  settingsKnown: boolean,
): FailureSummary => {
  const notConfigured = operation.failure_code === "PROVIDER_NOT_CONFIGURED";
  const missingProvider = settingsKnown && !providerUsable && notConfigured;
  const presentation = missingProvider
    ? missingProviderPresentation
    : notConfigured && providerUsable
      ? providerNowConfiguredPresentation
      : operation.failure_code == null
        ? null
        : failurePresentations[operation.failure_code];
  const detail = failureReasonDetail(operation.failure_reason);

  return {
    title: presentation?.title ?? statusLabels[operation.status],
    sentences: [
      ...(detail === null ? [] : [detail]),
      presentation?.guidance ??
        (operation.safe_failure_detail != null
          ? unknownFailureGuidance
          : (terminalSummaries[operation.status] ?? unknownFailureGuidance)),
    ],
    missingProvider,
  };
};
