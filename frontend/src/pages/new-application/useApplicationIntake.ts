import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import {
  acknowledgementApplies,
  createApplication,
  duplicateCheck,
  duplicateMatchesFromProblem,
  startAnalysis,
} from "../../api/applications";
import type { ApplicationIntake, DuplicateMatch } from "../../api/contracts";
import { ApiProblem, type ProblemDetails } from "../../api/client";
import { executionProvider, settingsQueryOptions } from "../../api/settings";
import { useAppForm } from "../../forms/useAppForm";

/* Native input affordances, not a second validation policy: they stop the user typing
   past a limit the server would refuse anyway. The refusal itself stays the server's. */
export const LABEL_MAX_CHARACTERS = 500;
export const SOURCE_URL_MAX_CHARACTERS = 2048;

export interface ApplicationIntakeFields {
  company: string;
  target_role: string;
  source_url: string;
  job_text: string;
}

const emptyIntakeFields: ApplicationIntakeFields = {
  company: "",
  target_role: "",
  source_url: "",
  job_text: "",
};

/* The job text is the exact content of the immutable JobSnapshot, so it is never
   trimmed or otherwise touched. The labels are, because a trailing space in a company
   name is a typo rather than evidence. */
export const intakeFrom = (fields: ApplicationIntakeFields): ApplicationIntake => {
  const sourceUrl = fields.source_url.trim();

  return {
    company: fields.company.trim(),
    target_role: fields.target_role.trim(),
    job_text: fields.job_text,
    source_url: sourceUrl === "" ? null : sourceUrl,
  };
};

interface SubmitInput {
  acknowledged: boolean;
  intake: ApplicationIntake;
}

type ApplicationIntakeResult =
  | { kind: "duplicates"; matches: DuplicateMatch[] }
  | {
      kind: "created";
      analysisProblem: ProblemDetails | null;
      analysisQueued: boolean;
      applicationId: string;
    };

interface UseApplicationIntakeOptions {
  onCreated: (result: Extract<ApplicationIntakeResult, { kind: "created" }>) => void;
}

/* Intake policy for the canonical NewApplicationPage: the mutation, the idempotency
   key, duplicate handling, and stale-answer detection stay outside its JSX. */
export const useApplicationIntake = ({ onCreated }: UseApplicationIntakeOptions) => {
  const queryClient = useQueryClient();
  const form = useAppForm<ApplicationIntakeFields>({ defaultValues: emptyIntakeFields });
  const { getValues, handleSubmit, watch } = form;

  const submit = useMutation<ApplicationIntakeResult, Error, SubmitInput>({
    mutationFn: async ({ acknowledged, intake }) => {
      /* Detection runs before creation for the user and again inside the create
         command. Once the user has acknowledged, the precheck is skipped so the
         acknowledgement is not immediately re-questioned by the finding it answered. */
      if (!acknowledged) {
        const matches = await duplicateCheck(intake);

        if (matches.length > 0) {
          return { kind: "duplicates", matches };
        }
      }

      const created = await createApplication(intake, acknowledged);

      /* Creation and analysis remain separate server commands: the snapshot must exist
         before an analyze Operation can name it. The intake action chains them for the
         user, with a source-derived key so an ambiguous accepted response can be retried
         without queueing a second analysis for this newly-created snapshot. */
      try {
        const { settings } = await queryClient.ensureQueryData(settingsQueryOptions);

        await startAnalysis(
          created.application_id,
          created.job_snapshot_id,
          `create:${created.application_id}:${created.job_snapshot_id}`,
          executionProvider(settings),
        );

        return {
          kind: "created",
          analysisProblem: null,
          analysisQueued: true,
          applicationId: created.application_id,
        };
      } catch (error) {
        /* The Application and its immutable snapshot already exist. Treating this as a
           failed creation would invite a retry that creates a duplicate; the caller
           navigates to the record and leaves its normal Analyze action available instead. */
        return {
          kind: "created",
          analysisProblem: error instanceof ApiProblem ? error.problem : null,
          analysisQueued: false,
          applicationId: created.application_id,
        };
      }
    },
    onSuccess: (result) => {
      if (result.kind === "created") {
        onCreated(result);
      }
    },
  });

  /* Read inside the form subscription below, which must not close over a stale
     mutation. The effect has no dependency list on purpose: it re-syncs after every
     render, which is exactly when the mutation state can have changed. */
  const submitStateRef = useRef({ hasResult: false, reset: () => {} });

  useEffect(() => {
    submitStateRef.current = {
      hasResult: submit.data !== undefined || submit.error !== null,
      reset: submit.reset,
    };
  });

  /* A duplicate decision belongs to the exact intake it was shown for. Editing a field
     while an answer is on screen withdraws it here; an answer still in flight when the
     edit happens has nothing to withdraw yet, and is caught by the comparison below. */
  useEffect(() => {
    const subscription = watch(() => {
      if (submitStateRef.current.hasResult) {
        submitStateRef.current.reset();
      }
    });

    return () => subscription.unsubscribe();
  }, [watch]);

  const runSubmit = (acknowledgedIntake: ApplicationIntake | undefined) =>
    handleSubmit((fields) => {
      const intake = intakeFrom(fields);

      submit.mutate({
        /* Never assumed: an acknowledgement is sent only when the text it was given for
           is still the text being created. */
        acknowledged: acknowledgementApplies(acknowledgedIntake, intake),
        intake,
      });
    });

  /* Two sources for the same answer: the precheck result, and the create command's own
     refusal. Neither is a failure of the request, so both leave the failure slot empty.
     Both are read off the one mutation rather than mirrored into component state, so
     there is no second copy to leave stale. */
  const answeredIntake = submit.variables?.intake;
  const acknowledgementRequired = duplicateMatchesFromProblem(submit.error);
  const settledMatches = acknowledgementRequired ?? (submit.data?.kind === "duplicates" ? submit.data.matches : null);
  /* The form stays editable while the precheck runs, so an answer can arrive describing
     text the user has already replaced. It is an answer about a different intake, and
     therefore not an answer about this one. */
  const answerIsCurrent = acknowledgementApplies(answeredIntake, intakeFrom(getValues()));
  const duplicates = answerIsCurrent ? settledMatches : null;
  const staleAnswer = !answerIsCurrent && settledMatches !== null;
  const failure = acknowledgementRequired === null ? submit.error : null;

  return {
    form,
    submit,
    runSubmit,
    duplicates,
    staleAnswer,
    failure,
    answeredIntake,
  };
};
