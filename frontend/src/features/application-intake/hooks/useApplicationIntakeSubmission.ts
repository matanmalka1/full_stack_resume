import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect, useMemo, useRef } from "react";

import { acknowledgementApplies, duplicateCheck, duplicateMatchesFromProblem } from "@/api/applications";
import type { ApplicationIntake, DuplicateMatch } from "@/api/contracts";
import { problemFieldErrors } from "@/ui/errorMessages";
import { createIntakeApplication, type CreatedIntakeApplication } from "../api/mutations";
import type { ApplicationIntakeFields } from "../model/applicationIntake";

interface SubmissionInput {
  acknowledged: boolean;
  intake: ApplicationIntake;
}

type SubmissionResult =
  | { kind: "duplicates"; matches: DuplicateMatch[] }
  | { kind: "created"; result: CreatedIntakeApplication }
  | { kind: "stale" };

interface UseApplicationIntakeSubmissionOptions {
  /* False only once Settings say no AI provider can analyze; the create then skips it. */
  analysisAvailable: boolean;
  currentIntake: ApplicationIntake;
  onCreated: (result: CreatedIntakeApplication, createdInputIsCurrent: boolean) => void;
}

type IntakeFieldErrors = Partial<Record<keyof ApplicationIntakeFields, string>>;

const intakeFields: readonly (keyof ApplicationIntakeFields)[] = ["company", "target_role", "source_url", "job_text"];

const isIntakeField = (value: string): value is keyof ApplicationIntakeFields =>
  (intakeFields as readonly string[]).includes(value);

/* The server's field refusals that belong to this form, with the shared short messages. */
const validationFieldErrors = (error: Error | null): IntakeFieldErrors | null => {
  const errors: IntakeFieldErrors = {};
  for (const [field, message] of problemFieldErrors(error)) {
    if (isIntakeField(field)) errors[field] = message;
  }
  return Object.keys(errors).length === 0 ? null : errors;
};

/* Owns only the asynchronous intake command. Form state stays with the page, while this
   hook makes duplicate answers safe to render only for the exact intake they describe. */
export const useApplicationIntakeSubmission = ({
  analysisAvailable,
  currentIntake,
  onCreated,
}: UseApplicationIntakeSubmissionOptions) => {
  const queryClient = useQueryClient();
  const currentIntakeRef = useRef(currentIntake);
  useLayoutEffect(() => {
    currentIntakeRef.current = currentIntake;
  }, [currentIntake]);
  const mutation = useMutation<SubmissionResult, Error, SubmissionInput>({
    mutationFn: async ({ acknowledged, intake }) => {
      if (!acknowledged) {
        const matches = await duplicateCheck(intake);
        if (matches.length > 0) return { kind: "duplicates", matches };
        /* A zero-match answer is stale too. Creating here used to persist the old
           posting after the user had already replaced it while the check was running. */
        if (!acknowledgementApplies(intake, currentIntakeRef.current)) return { kind: "stale" };
      }

      return {
        kind: "created",
        result: await createIntakeApplication(queryClient, intake, acknowledged, analysisAvailable),
      };
    },
    onSuccess: (outcome, input) => {
      if (outcome.kind === "created") {
        onCreated(outcome.result, acknowledgementApplies(input.intake, currentIntakeRef.current));
      }
    },
  });

  const submittedIntake = mutation.variables?.intake;
  const duplicateMatches =
    duplicateMatchesFromProblem(mutation.error) ??
    (mutation.data?.kind === "duplicates" ? mutation.data.matches : null);
  const answerIsCurrent = acknowledgementApplies(submittedIntake, currentIntake);
  const responseIsSettled = mutation.data !== undefined || mutation.error !== null;
  const parsedFieldErrors = useMemo(() => validationFieldErrors(mutation.error), [mutation.error]);
  const fieldErrors = answerIsCurrent ? parsedFieldErrors : null;

  return {
    duplicateMatches: answerIsCurrent ? duplicateMatches : null,
    error: answerIsCurrent && duplicateMatchesFromProblem(mutation.error) === null ? mutation.error : null,
    fieldErrors,
    isStale: responseIsSettled && !answerIsCurrent,
    isSubmitting: mutation.isPending,
    submit: (intake: ApplicationIntake, acknowledged = false) => mutation.mutate({ intake, acknowledged }),
    resetSettledResult: () => {
      if (!mutation.isPending) mutation.reset();
    },
  };
};
