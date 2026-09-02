import { useEffect } from "react";

import { JOB_TEXT_MAX_BYTES } from "../../api/applications";
import { ErrorCallout } from "../../app/ErrorCallout";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Dialog } from "../../ui/Dialog";
import { Field } from "../../ui/Field";
import { TextArea, TextInput } from "../../ui/TextInput";
import { DuplicateChoices } from "../new-application/DuplicateChoices";
import {
  type ApplicationIntakeResult,
  LABEL_MAX_CHARACTERS,
  SOURCE_URL_MAX_CHARACTERS,
  emptyIntakeFields,
  useApplicationIntake,
} from "../new-application/useApplicationIntake";

const FORM_ID = "quick-application-intake";

interface QuickIntakeDialogProps {
  onClose: () => void;
  onCreated: (
    applicationId: string,
    analysisQueued: boolean,
    analysisProblem: Extract<ApplicationIntakeResult, { kind: "created" }>["analysisProblem"],
  ) => void;
  open: boolean;
}

export const QuickIntakeDialog = ({ onClose, onCreated, open }: QuickIntakeDialogProps) => {
  const { answeredIntake, duplicates, failure, form, runSubmit, staleAnswer, submit } = useApplicationIntake({
    onCreated: (result) => onCreated(result.applicationId, result.analysisQueued, result.analysisProblem),
  });
  const {
    formState: { errors },
    register,
    reset,
  } = form;

  useEffect(() => {
    if (!open) {
      reset(emptyIntakeFields);
      submit.reset();
    }
  }, [open, reset, submit.reset]);

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
