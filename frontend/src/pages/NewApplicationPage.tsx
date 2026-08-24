import { useMutation } from "@tanstack/react-query";
import { type ChangeEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  JOB_TEXT_MAX_BYTES,
  createApplication,
  duplicateCheck,
  duplicateMatchesFromProblem,
} from "../api/applications";
import { ApiProblem } from "../api/client";
import type {
  ApplicationIntake,
  DuplicateMatch,
  DuplicateMatchReason,
} from "../api/contracts";
import { useAppForm } from "../forms/useAppForm";
import { ActionBar } from "../ui/ActionBar";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { Field } from "../ui/Field";
import { LiveRegion } from "../ui/LiveRegion";
import { LtrText } from "../ui/LtrText";
import { PageHeading } from "../ui/PageHeading";
import { TechnicalDetails } from "../ui/TechnicalDetails";
import { TextArea, TextInput } from "../ui/TextInput";

/* Native input affordances, not a second validation policy: they stop the user typing
   past a limit the server would refuse anyway. The refusal itself stays the server's. */
const LABEL_MAX_CHARACTERS = 500;
const SOURCE_URL_MAX_CHARACTERS = 2048;

/* Keyed by the generated union, so a detection reason added to the backend fails the
   frontend build instead of reaching the screen as an untranslated code. */
const matchReasonLabels: Record<DuplicateMatchReason, string> = {
  source_url: "אותה כתובת מקור",
  normalized_text: "טקסט משרה זהה",
  company_title: "אותה חברה ואותו תפקיד",
};

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

const isLocalTextFile = (file: File): boolean =>
  file.type === "text/plain" || /\.txt$/i.test(file.name);

export const NewApplicationPage = () => {
  const navigate = useNavigate();
  const {
    formState: { errors },
    handleSubmit,
    register,
    setValue,
    watch,
  } = useAppForm<NewApplicationFields>({ defaultValues: emptyFields });

  const [loadedFileName, setLoadedFileName] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | undefined>(undefined);

  const submit = useMutation<SubmitResult, Error, SubmitInput>({
    mutationFn: async ({ acknowledged, intake }) => {
      /* Detection runs before creation for the user and again inside the create
         command. Once the user has acknowledged, the precheck is skipped so the
         acknowledgement is not immediately re-questioned by the same finding. */
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
        /* Creation never implies an AI call: the analysis screen is where the explicit
           `ניתוח המשרה` action lives, and it reads the application projection itself. */
        void navigate(`/applications/${encodeURIComponent(result.applicationId)}/analysis`);
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

  /* A duplicate decision belongs to the exact intake it was shown for. Editing any
     field withdraws it, so an acknowledgement can never be carried onto text the user
     changed after the candidates were listed. */
  useEffect(() => {
    const subscription = watch(() => {
      if (submitStateRef.current.hasResult) {
        submitStateRef.current.reset();
      }
    });

    return () => subscription.unsubscribe();
  }, [watch]);

  const readLocalFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];

    if (file === undefined) {
      return;
    }

    setLoadedFileName(null);

    if (!isLocalTextFile(file)) {
      setFileError("ניתן לבחור קובץ טקסט בלבד, עם סיומת txt.");
      return;
    }

    if (file.size > JOB_TEXT_MAX_BYTES) {
      setFileError("הקובץ גדול מדי. ניתן להדביק את הטקסט הרלוונטי ישירות לשדה שלמטה.");
      return;
    }

    try {
      const text = await file.text();

      setFileError(undefined);
      setValue("job_text", text, { shouldDirty: true, shouldValidate: true });
      setLoadedFileName(file.name);
    } catch {
      setFileError("קריאת הקובץ נכשלה. ניתן להדביק את הטקסט ידנית לשדה שלמטה.");
    }
  };

  const runSubmit = (acknowledged: boolean) =>
    handleSubmit((fields) => {
      submit.mutate({ acknowledged, intake: intakeFrom(fields) });
    });

  /* Two sources for the same answer: the precheck result, and the create command's own
     refusal. Neither is a failure of the request, so both leave the failure slot empty.
     Both are read off the one mutation rather than mirrored into component state, so a
     new submit withdraws the previous answer by itself and there is no second copy to
     leave stale. */
  const acknowledgementRequired = duplicateMatchesFromProblem(submit.error);
  const precheckMatches = submit.data?.kind === "duplicates" ? submit.data.matches : null;
  const duplicates = acknowledgementRequired ?? precheckMatches;
  const failure = acknowledgementRequired === null ? submit.error : null;

  return (
    <Card aria-labelledby="route-heading">
      <PageHeading
        description="הזנת פרטי המשרה יוצרת מועמדות ותצלום משרה קבוע. ניתוח המשרה הוא פעולה נפרדת ואינו מופעל מעצמו."
        id="route-heading"
      >
        משרה חדשה
      </PageHeading>

      <form className="mt-8 flex flex-col gap-6" noValidate onSubmit={runSubmit(false)}>
        <div className="grid gap-6 md:grid-cols-2">
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

        <Field
          error={fileError}
          hint="הקובץ נקרא בדפדפן וממלא את שדה טקסט המשרה. שום קובץ אינו נשלח לשרת."
          label="קריאת קובץ טקסט מהמחשב (לא חובה)"
        >
          {(control) => (
            <input
              {...control}
              accept=".txt,text/plain"
              className="block w-full text-support text-cv-text file:me-3 file:min-h-11 file:rounded-control file:border file:border-cv-border-strong file:bg-cv-surface-muted file:px-4 file:text-support file:font-medium file:text-cv-text"
              onChange={(event) => {
                void readLocalFile(event);
              }}
              type="file"
            />
          )}
        </Field>

        {loadedFileName === null ? null : (
          <LiveRegion className="text-support text-cv-text-muted" visuallyHidden={false}>
            הטקסט מהקובץ <LtrText>{loadedFileName}</LtrText> נטען לשדה טקסט המשרה.
          </LiveRegion>
        )}

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

        {duplicates === null ? null : (
          <Callout
            action={
              <Button
                disabled={submit.isPending}
                onClick={() => {
                  void runSubmit(true)();
                }}
                variant="secondary"
              >
                יצירה בכל זאת
              </Button>
            }
            role="alert"
            title="נמצאו מועמדויות דומות"
            tone="warning"
          >
            <p>
              זו אזהרה בלבד ואינה חוסמת. אפשר לפתוח מועמדות קיימת, או ליצור מועמדות נוספת
              עם הטקסט שהוזן באמצעות הכפתור שבהמשך.
            </p>

            {duplicates.length === 0 ? (
              <p className="mt-3">השרת ביקש אישור מפורש אך לא החזיר פירוט של המועמדויות הדומות.</p>
            ) : (
              <ul className="mt-3 flex flex-col gap-3">
                {duplicates.map((match) => (
                  <li
                    className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-cv-border bg-cv-surface p-3"
                    key={match.application_id}
                  >
                    <div className="min-w-0">
                      <p className="font-medium text-cv-text" dir="auto">
                        {match.company}
                      </p>
                      <p className="text-cv-text-muted" dir="auto">
                        {match.target_role}
                      </p>
                      <p className="text-cv-text-muted">
                        {match.matched_on
                          .map((reason) => matchReasonLabels[reason])
                          .join(" · ")}
                      </p>
                    </div>
                    <Link
                      className={buttonClasses("secondary")}
                      to={`/applications/${encodeURIComponent(match.application_id)}`}
                    >
                      פתיחת המועמדות הקיימת
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Callout>
        )}

        {failure === null ? null : (
          <Callout
            role="alert"
            title={
              failure instanceof ApiProblem ? failure.problem.title : "יצירת המועמדות נכשלה"
            }
            tone="blocker"
          >
            {failure instanceof ApiProblem
              ? failure.problem.detail
              : "הפנייה לשרת נכשלה. מה שהוזן נשמר בטופס וניתן לנסות שוב."}
            {failure instanceof ApiProblem ? (
              <TechnicalDetails className="mt-3">
                <LtrText>{failure.problem.code}</LtrText>
              </TechnicalDetails>
            ) : null}
          </Callout>
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
