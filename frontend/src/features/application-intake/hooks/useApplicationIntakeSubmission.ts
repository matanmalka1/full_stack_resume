import { useMutation, useQueryClient } from "@tanstack/react-query";

import { acknowledgementApplies, duplicateCheck, duplicateMatchesFromProblem } from "@/api/applications";
import type { ApplicationIntake, DuplicateMatch } from "@/api/contracts";
import { createIntakeApplication, type CreatedIntakeApplication } from "../api/createApplication";

interface SubmissionInput {
  acknowledged: boolean;
  intake: ApplicationIntake;
}

type SubmissionResult =
  { kind: "duplicates"; matches: DuplicateMatch[] } | { kind: "created"; result: CreatedIntakeApplication };

interface UseApplicationIntakeSubmissionOptions {
  currentIntake: ApplicationIntake;
  onCreated: (result: CreatedIntakeApplication) => void;
}

/* Owns only the asynchronous intake command. Form state stays with the page, while this
   hook makes duplicate answers safe to render only for the exact intake they describe. */
export const useApplicationIntakeSubmission = ({ currentIntake, onCreated }: UseApplicationIntakeSubmissionOptions) => {
  const queryClient = useQueryClient();
  const mutation = useMutation<SubmissionResult, Error, SubmissionInput>({
    mutationFn: async ({ acknowledged, intake }) => {
      if (!acknowledged) {
        const matches = await duplicateCheck(intake);
        if (matches.length > 0) return { kind: "duplicates", matches };
      }

      return { kind: "created", result: await createIntakeApplication(queryClient, intake, acknowledged) };
    },
    onSuccess: (outcome) => {
      if (outcome.kind === "created") onCreated(outcome.result);
    },
  });

  const submittedIntake = mutation.variables?.intake;
  const duplicateMatches =
    duplicateMatchesFromProblem(mutation.error) ??
    (mutation.data?.kind === "duplicates" ? mutation.data.matches : null);
  const answerIsCurrent = acknowledgementApplies(submittedIntake, currentIntake);

  return {
    duplicateMatches: answerIsCurrent ? duplicateMatches : null,
    error: duplicateMatchesFromProblem(mutation.error) === null ? mutation.error : null,
    isStale: !answerIsCurrent && duplicateMatches !== null,
    isSubmitting: mutation.isPending,
    submit: (intake: ApplicationIntake, acknowledged = false) => mutation.mutate({ intake, acknowledged }),
    resetSettledResult: () => {
      if (!mutation.isPending) mutation.reset();
    },
  };
};
