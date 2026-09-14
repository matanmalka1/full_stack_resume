import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLayoutEffect, useMemo, useRef } from "react";

import { acknowledgementApplies, duplicateCheck, duplicateMatchesFromProblem } from "@/api/applications";
import { ApiProblem } from "@/api/client";
import type { ApplicationIntake, DuplicateMatch } from "@/api/contracts";
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
  currentIntake: ApplicationIntake;
  onCreated: (result: CreatedIntakeApplication, createdInputIsCurrent: boolean) => void;
}

type IntakeFieldErrors = Partial<Record<keyof ApplicationIntakeFields, string>>;

const fieldMessages: Record<keyof ApplicationIntakeFields, string> = {
  company: "שם החברה אינו עומד בדרישות השרת. יש לבדוק את הערך.",
  target_role: "תפקיד היעד אינו עומד בדרישות השרת. יש לבדוק את הערך.",
  source_url: "כתובת המשרה אינה עומדת בדרישות השרת. יש לבדוק את הכתובת.",
  job_text: "טקסט המשרה אינו עומד בדרישות השרת. יש לבדוק את התוכן והאורך.",
};

const isIntakeField = (value: unknown): value is keyof ApplicationIntakeFields =>
  typeof value === "string" && Object.hasOwn(fieldMessages, value);

const validationFieldErrors = (error: Error | null): IntakeFieldErrors | null => {
  if (!(error instanceof ApiProblem)) return null;

  if (error.problem.code === "APPLICATION_INTAKE_INVALID") {
    const field = error.problem.context?.field;
    return isIntakeField(field) ? { [field]: fieldMessages[field] } : null;
  }
  if (error.problem.code !== "REQUEST_VALIDATION_FAILED") return null;

  const issues = error.problem.context?.issues;
  if (!Array.isArray(issues)) return null;

  const errors: IntakeFieldErrors = {};
  for (const issue of issues) {
    if (typeof issue !== "object" || issue === null) continue;
    const location = (issue as Record<string, unknown>).location;
    if (!Array.isArray(location)) continue;

    let field: keyof ApplicationIntakeFields | undefined;
    for (let index = location.length - 1; index >= 0; index -= 1) {
      const part: unknown = location[index];
      if (isIntakeField(part)) {
        field = part;
        break;
      }
    }
    if (field !== undefined) errors[field] = fieldMessages[field];
  }
  return Object.keys(errors).length === 0 ? null : errors;
};

/* Owns only the asynchronous intake command. Form state stays with the page, while this
   hook makes duplicate answers safe to render only for the exact intake they describe. */
export const useApplicationIntakeSubmission = ({ currentIntake, onCreated }: UseApplicationIntakeSubmissionOptions) => {
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

      return { kind: "created", result: await createIntakeApplication(queryClient, intake, acknowledged) };
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
    error:
      answerIsCurrent && duplicateMatchesFromProblem(mutation.error) === null && fieldErrors === null
        ? mutation.error
        : null,
    fieldErrors,
    isStale: responseIsSettled && !answerIsCurrent,
    isSubmitting: mutation.isPending,
    submit: (intake: ApplicationIntake, acknowledged = false) => mutation.mutate({ intake, acknowledged }),
    resetSettledResult: () => {
      if (!mutation.isPending) mutation.reset();
    },
  };
};
