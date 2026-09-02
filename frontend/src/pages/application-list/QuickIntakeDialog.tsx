import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import {
  JOB_TEXT_MAX_BYTES,
  acknowledgementApplies,
  createApplication,
  duplicateCheck,
  duplicateMatchesFromProblem,
  startAnalysis,
} from "../../api/applications";
import type { ApplicationIntake, DuplicateMatch } from "../../api/contracts";
import { executionProvider, settingsQueryOptions } from "../../api/settings";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Dialog } from "../../ui/Dialog";
import { Field } from "../../ui/Field";
import { TextArea, TextInput } from "../../ui/TextInput";
import { DuplicateChoices } from "../new-application/DuplicateChoices";

const LABEL_MAX_CHARACTERS = 500;
const SOURCE_URL_MAX_CHARACTERS = 2048;
const FORM_ID = "quick-application-intake";

interface QuickIntakeFields {
  company: string;
  target_role: string;
  source_url: string;
  job_text: string;
}

const emptyFields: QuickIntakeFields = {
  company: "",
  target_role: "",
  source_url: "",
  job_text: "",
};

const intakeFrom = (fields: QuickIntakeFields): ApplicationIntake => {
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

type SubmitResult =
  | { kind: "duplicates"; matches: DuplicateMatch[] }
  | { kind: "created"; analysisQueued: boolean; applicationId: string };

interface QuickIntakeDialogProps {
  onClose: () => void;
  onCreated: (applicationId: string, analysisQueued: boolean) => void;
  open: boolean;
}

export const QuickIntakeDialog = ({ onClose, onCreated, open }: QuickIntakeDialogProps) => {
  const queryClient = useQueryClient();
  const {
    formState: { errors },
    getValues,
    handleSubmit,
    register,
    reset,
    watch,
  } = useAppForm<QuickIntakeFields>({ defaultValues: emptyFields });

  const submit = useMutation<SubmitResult, Error, SubmitInput>({
    mutationFn: async ({ acknowledged, intake }) => {
      if (!acknowledged) {
        const matches = await duplicateCheck(intake);

        if (matches.length > 0) {
          return { kind: "duplicates", matches };
        }
      }

      const created = await createApplication(intake, acknowledged);

      try {
        const { settings } = await queryClient.ensureQueryData(settingsQueryOptions);
        await startAnalysis(
          created.application_id,
          created.job_snapshot_id,
          `create:${created.application_id}:${created.job_snapshot_id}`,
          executionProvider(settings),
        );
        return { kind: "created", analysisQueued: true, applicationId: created.application_id };
      } catch {
        return { kind: "created", analysisQueued: false, applicationId: created.application_id };
      }
    },
    onSuccess: (result) => {
      if (result.kind === "created") {
        onCreated(result.applicationId, result.analysisQueued);
      }
    },
  });

  const submitStateRef = useRef({ hasResult: false, reset: () => {} });

  useEffect(() => {
    submitStateRef.current = {
      hasResult: submit.data !== undefined || submit.error !== null,
      reset: submit.reset,
    };
  });

  useEffect(() => {
    const subscription = watch(() => {
      if (submitStateRef.current.hasResult) {
        submitStateRef.current.reset();
      }
    });
    return () => subscription.unsubscribe();
  }, [watch]);

  useEffect(() => {
    if (!open) {
      reset(emptyFields);
      submit.reset();
    }
  }, [open, reset, submit.reset]);

  const runSubmit = (acknowledgedIntake: ApplicationIntake | undefined) =>
    handleSubmit((fields) => {
      const intake = intakeFrom(fields);
      submit.mutate({ acknowledged: acknowledgementApplies(acknowledgedIntake, intake), intake });
    });

  const answeredIntake = submit.variables?.intake;
  const acknowledgementRequired = duplicateMatchesFromProblem(submit.error);
  const settledMatches = acknowledgementRequired ?? (submit.data?.kind === "duplicates" ? submit.data.matches : null);
  const answerIsCurrent = acknowledgementApplies(answeredIntake, intakeFrom(getValues()));
  const duplicates = answerIsCurrent ? settledMatches : null;
  const staleAnswer = !answerIsCurrent && settledMatches !== null;
  const failure = acknowledgementRequired === null ? submit.error : null;

  return (
    <Dialog
      dismissible={!submit.isPending}
      footer={
        <>
          <Button disabled={submit.isPending} onClick={onClose} variant="secondary">
            ביטול
          </Button>
          <Button
            disabled={submit.isPending && submit.variables?.acknowledged === true}
            form={FORM_ID}
            pending={submit.isPending && submit.variables?.acknowledged !== true}
            pendingLabel="בודק כפילויות…"
            type="submit"
          >
            קליטת משרה
          </Button>
        </>
      }
      headingId="quick-intake-heading"
      onClose={onClose}
      open={open}
      title="קליטת משרה מהירה"
    >
      <p className="mb-4 text-support text-cv-text-muted">
        הזנת הפרטים שומרת תצלום קבוע של המשרה ומתחילה את ניתוח ההתאמה.
      </p>
      <form className="flex flex-col gap-4" id={FORM_ID} noValidate onSubmit={runSubmit(undefined)}>
        {failure === null ? null : (
          <ErrorCallout
            error={failure}
            fallbackDetail="הפרטים נשמרו בטופס וניתן לנסות שוב."
            fallbackTitle="קליטת המשרה נכשלה"
          />
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          <Field error={errors.company?.message} label="שם החברה">
            {(control) => (
              <TextInput
                {...control}
                {...register("company", { validate: (value) => value.trim() !== "" || "יש להזין את שם החברה." })}
                autoComplete="organization"
                dir="auto"
                maxLength={LABEL_MAX_CHARACTERS}
              />
            )}
          </Field>
          <Field error={errors.target_role?.message} label="תפקיד היעד">
            {(control) => (
              <TextInput
                {...control}
                {...register("target_role", {
                  validate: (value) => value.trim() !== "" || "יש להזין את תפקיד היעד.",
                })}
                dir="auto"
                maxLength={LABEL_MAX_CHARACTERS}
              />
            )}
          </Field>
        </div>

        <Field label="כתובת המשרה" optional>
          {(control) => (
            <TextInput
              {...control}
              {...register("source_url")}
              className="ltr-island"
              dir="ltr"
              inputMode="url"
              maxLength={SOURCE_URL_MAX_CHARACTERS}
            />
          )}
        </Field>

        <Field error={errors.job_text?.message} label="טקסט המשרה">
          {(control) => (
            <TextArea
              {...control}
              {...register("job_text", {
                validate: {
                  required: (value) => value.trim() !== "" || "יש להזין את טקסט המשרה.",
                  withinBudget: (value) =>
                    new TextEncoder().encode(value).length <= JOB_TEXT_MAX_BYTES || "טקסט המשרה חורג מהגודל המותר.",
                },
              })}
              className="h-40 max-h-[40vh]"
              dir="auto"
              placeholder="הדבק כאן את תיאור המשרה…"
            />
          )}
        </Field>

        {duplicates === null ? null : (
          <DuplicateChoices
            matches={duplicates}
            onCreateAnyway={() => {
              void runSubmit(answeredIntake)();
            }}
            pending={submit.isPending}
          />
        )}

        {staleAnswer ? (
          <Callout role="status" title="הקלט השתנה מאז הבדיקה" tone="neutral">
            תוצאת בדיקת הכפילויות אינה חלה על הפרטים הנוכחיים. יש לשלוח שוב כדי לבדוק אותם.
          </Callout>
        ) : null}
      </form>
    </Dialog>
  );
};
