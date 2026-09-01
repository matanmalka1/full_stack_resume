import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

import {
  JOB_TEXT_MAX_BYTES,
  acknowledgementApplies,
  createApplication,
  duplicateCheck,
  duplicateMatchesFromProblem,
  startAnalysis,
} from "../api/applications";
import type { ApplicationIntake, DuplicateMatch } from "../api/contracts";
import { executionProvider, settingsQueryOptions } from "../api/settings";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { useAppForm } from "../forms/useAppForm";
import { ActionBar } from "../ui/ActionBar";
import { Button } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Field } from "../ui/Field";
import { FormSection } from "../ui/FormSection";
import { LtrText } from "../ui/LtrText";
import { PageShell } from "../ui/PageShell";
import { TextArea, TextInput } from "../ui/TextInput";
import { cx } from "../ui/cx";
import { DuplicateChoices } from "./new-application/DuplicateChoices";
import { JobTextFileField } from "./new-application/JobTextFileField";

/* Native input affordances, not a second validation policy: they stop the user typing
   past a limit the server would refuse anyway. The refusal itself stays the server's. */
const LABEL_MAX_CHARACTERS = 500;
const SOURCE_URL_MAX_CHARACTERS = 2048;

/* The snapshot limit the server enforces is a byte budget, not a character count, so the
   counter measures the same thing the refusal will. It stays a quiet character count
   until the text is close enough to the ceiling for the budget to be the useful fact. */
const JOB_TEXT_BUDGET_NOTICE_RATIO = 0.8;

const formatMebibytes = (bytes: number): string =>
  `${(bytes / (1024 * 1024)).toLocaleString("en-US", { maximumFractionDigits: 2 })} MB`;

interface NewApplicationFields {
  company: string;
  target_role: string;
  source_url: string;
  job_text: string;
}

const emptyFields: NewApplicationFields = {
  company: "",
  target_role: "",
  source_url: "",
  job_text: "",
};

/* The job text is the exact content of the immutable JobSnapshot, so it is never
   trimmed or otherwise touched. The labels are, because a trailing space in a company
   name is a typo rather than evidence. */
const intakeFrom = (fields: NewApplicationFields): ApplicationIntake => {
  const sourceUrl = fields.source_url.trim();

  return {
    company: fields.company.trim(),
    target_role: fields.target_role.trim(),
    job_text: fields.job_text,
    source_url: sourceUrl === "" ? null : sourceUrl,
  };
};

interface SubmitInput {
  intake: ApplicationIntake;
  acknowledged: boolean;
}

type SubmitResult =
  | { kind: "duplicates"; matches: DuplicateMatch[] }
  | { kind: "created"; analysisQueued: boolean; applicationId: string };

export const NewApplicationPage = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  /* The intake screen is the one place `intake` is the projection's own answer, so it
     states it rather than relying on the landmark's initial value. */
  useWorkflowStage("intake");
  const {
    formState: { errors },
    getValues,
    handleSubmit,
    register,
    setValue,
    watch,
  } = useAppForm<NewApplicationFields>({ defaultValues: emptyFields });

  const submit = useMutation<SubmitResult, Error, SubmitInput>({
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
          analysisQueued: true,
          applicationId: created.application_id,
        };
      } catch {
        /* The Application and its immutable snapshot already exist. Treating this as a
           failed creation would invite a retry that creates a duplicate; navigate to the
           record and let its normal Analyze action remain available instead. */
        return {
          kind: "created",
          analysisQueued: false,
          applicationId: created.application_id,
        };
      }
    },
    onSuccess: (result) => {
      if (result.kind === "created") {
        void navigate(`/applications/${encodeURIComponent(result.applicationId)}`, {
          state: result.analysisQueued ? undefined : { automaticAnalysisStartFailed: true },
        });
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

  /* The snapshot is written exactly as entered, so its size is worth showing while it is
     still editable. Subscribing to this one field keeps the counter live without making
     the whole form controlled. */
  const jobText = watch("job_text");
  const jobTextLength = jobText.length;
  /* Measured only once the text is long enough to be worth measuring: encoding every
     keystroke of a short paste to report a fraction of a percent is work for nothing. */
  const jobTextBytes =
    jobTextLength * 4 < JOB_TEXT_MAX_BYTES * JOB_TEXT_BUDGET_NOTICE_RATIO
      ? null
      : new TextEncoder().encode(jobText).length;
  const jobTextNearBudget =
    jobTextBytes !== null && jobTextBytes >= JOB_TEXT_MAX_BYTES * JOB_TEXT_BUDGET_NOTICE_RATIO;
  const jobTextOverBudget = jobTextBytes !== null && jobTextBytes > JOB_TEXT_MAX_BYTES;

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
  const settledMatches =
    acknowledgementRequired ?? (submit.data?.kind === "duplicates" ? submit.data.matches : null);
  /* The form stays editable while the precheck runs, so an answer can arrive describing
     text the user has already replaced. It is an answer about a different intake, and
     therefore not an answer about this one. */
  const answerIsCurrent = acknowledgementApplies(answeredIntake, intakeFrom(getValues()));
  const duplicates = answerIsCurrent ? settledMatches : null;
  const staleAnswer = !answerIsCurrent && settledMatches !== null;
  const failure = acknowledgementRequired === null ? submit.error : null;

  return (
    <PageShell
      description="הזנת פרטי המשרה יוצרת מועמדות ותצלום משרה קבוע, ולאחר השמירה מפעילה את ניתוח המשרה."
      title="משרה חדשה"
    >
      <form className="flex flex-col gap-6" noValidate onSubmit={runSubmit(undefined)}>
        <FormSection
          description="שלושת אלה מזהים את המועמדות ברשימות ובכל מסכי ההמשך."
          title="פרטי המשרה"
        >
          <div className="grid gap-4 md:grid-cols-2">
            <Field error={errors.company?.message} label="שם החברה">
              {(control) => (
                <TextInput
                  {...control}
                  {...register("company", {
                    validate: (value) => value.trim() !== "" || "יש להזין את שם החברה.",
                  })}
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

          <Field
            hint="הכתובת נשמרת כתיעוד מקור בלבד. המערכת אינה פותחת אותה ואינה מייבאת ממנה טקסט."
            label="כתובת המשרה (לא חובה)"
          >
            {(control) => (
              /* A.3: a URL is an LTR island even inside the RTL shell. */
              <TextInput
                {...control}
                {...register("source_url")}
                className="ltr-island max-w-xl"
                dir="ltr"
                inputMode="url"
                maxLength={SOURCE_URL_MAX_CHARACTERS}
              />
            )}
          </Field>
        </FormSection>

        <FormSection
          aside={
            jobTextLength === 0 ? null : jobTextNearBudget ? (
              /* Close to the ceiling the byte budget is the fact that matters, so the
                 counter switches to it and says which side of the limit the text is on
                 before the server has to. */
              <span
                className={cx(
                  "font-medium",
                  jobTextOverBudget ? "text-cv-blocker" : "text-cv-warning",
                )}
              >
                <LtrText>
                  {formatMebibytes(jobTextBytes ?? 0)} / {formatMebibytes(JOB_TEXT_MAX_BYTES)}
                </LtrText>{" "}
                {jobTextOverBudget ? "— חורג מגודל התצלום המותר" : "מגודל התצלום המותר"}
              </span>
            ) : (
              <span>
                <LtrText>{jobTextLength.toLocaleString("en-US")}</LtrText> תווים
              </span>
            )
          }
          className="rounded-surface border border-cv-border bg-cv-surface-muted/60 p-4"
          description="הטקסט נשמר כתצלום משרה קבוע ואינו משתנה אחרי היצירה. הוא נשמר בדיוק כפי שהוזן."
          title="תצלום המשרה"
        >
          <JobTextFileField
            onText={(text) =>
              setValue("job_text", text, { shouldDirty: true, shouldValidate: true })
            }
          />

          <Field error={errors.job_text?.message} label="טקסט המשרה">
            {(control) => (
              /* Mixed Hebrew/English job text picks its own direction (A.3). */
              <TextArea
                {...control}
                {...register("job_text", {
                  validate: (value) => value.trim() !== "" || "יש להזין את טקסט המשרה.",
                })}
                /* The payload of the whole screen. It opens tall enough to read a
                   posting in, grows with a paste rather than hiding it behind a
                   scrollbar, and stops at the viewport so the submit stays reachable. */
                className="min-h-64 max-h-[60vh] [field-sizing:content]"
                dir="auto"
              />
            )}
          </Field>
        </FormSection>

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
            בדיקת הכפילויות רצה על טקסט קודם, ולכן התשובה שלה אינה חלה על מה שמופיע עכשיו.
            יש ללחוץ שוב על יצירת מועמדות כדי לבדוק את הקלט הנוכחי.
          </Callout>
        ) : null}

        {failure === null ? null : (
          <ErrorCallout
            error={failure}
            fallbackDetail="הפנייה לשרת נכשלה. מה שהוזן נשמר בטופס וניתן לנסות שוב."
            fallbackTitle="יצירת המועמדות נכשלה"
          />
        )}

        <ActionBar
          primary={
            <Button
              disabled={submit.isPending && submit.variables?.acknowledged === true}
              pending={submit.isPending && submit.variables?.acknowledged !== true}
              pendingLabel="בודק כפילויות…"
              type="submit"
            >
              יצירת מועמדות
            </Button>
          }
          sticky
        />
      </form>
    </PageShell>
  );
};
