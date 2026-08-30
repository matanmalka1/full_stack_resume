import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

import {
  acknowledgementApplies,
  createApplication,
  duplicateCheck,
  duplicateMatchesFromProblem,
} from "../api/applications";
import type { ApplicationIntake, DuplicateMatch } from "../api/contracts";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { useAppForm } from "../forms/useAppForm";
import { ActionBar } from "../ui/ActionBar";
import { Button } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { Field } from "../ui/Field";
import { FormSection } from "../ui/FormSection";
import { LtrText } from "../ui/LtrText";
import { PageHeading } from "../ui/PageHeading";
import { TextArea, TextInput } from "../ui/TextInput";
import { DuplicateChoices } from "./DuplicateChoices";
import { JobTextFileField } from "./JobTextFileField";

/* Native input affordances, not a second validation policy: they stop the user typing
   past a limit the server would refuse anyway. The refusal itself stays the server's. */
const LABEL_MAX_CHARACTERS = 500;
const SOURCE_URL_MAX_CHARACTERS = 2048;

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
  | { kind: "created"; applicationId: string };

export const NewApplicationPage = () => {
  const navigate = useNavigate();
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

      return { kind: "created", applicationId: created.application_id };
    },
    onSuccess: (result) => {
      if (result.kind === "created") {
        /* Creation never implies an AI call. The application context screen is where the
           explicit `ניתוח המשרה` action lives, and it reads the projection itself, so a
           newly created Application and one opened from a duplicate reach the same place. */
        void navigate(`/applications/${encodeURIComponent(result.applicationId)}`);
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
  const jobTextLength = watch("job_text").length;

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
    <Card aria-labelledby="route-heading">
      <PageHeading
        description="הזנת פרטי המשרה יוצרת מועמדות ותצלום משרה קבוע. ניתוח המשרה הוא פעולה נפרדת ואינו מופעל מעצמו."
        id="route-heading"
      >
        משרה חדשה
      </PageHeading>

      <form className="mt-8 flex flex-col gap-8" noValidate onSubmit={runSubmit(undefined)}>
        <FormSection
          description="שלושת אלה מזהים את המועמדות ברשימות ובכל מסכי ההמשך."
          title="פרטי המשרה"
        >
          <div className="grid gap-5 md:grid-cols-2">
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
                className="ltr-island"
                dir="ltr"
                inputMode="url"
                maxLength={SOURCE_URL_MAX_CHARACTERS}
              />
            )}
          </Field>
        </FormSection>

        <FormSection
          aside={
            jobTextLength === 0 ? null : (
              <span>
                <LtrText>{jobTextLength.toLocaleString("en-US")}</LtrText> תווים
              </span>
            )
          }
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
                className="min-h-64"
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
          className="mt-2"
          primary={
            <Button disabled={submit.isPending} type="submit">
              {submit.isPending && submit.variables?.acknowledged !== true
                ? "בודק כפילויות…"
                : "יצירת מועמדות"}
            </Button>
          }
        />
      </form>
    </Card>
  );
};
