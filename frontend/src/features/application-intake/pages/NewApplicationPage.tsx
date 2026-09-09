import { ArrowRight, Sparkles } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { boardPath } from "@/app/boardReturn";
import { routePaths } from "@/app/routePaths";
import { CommitBar, NEXT_STEP_LABEL, WizardStepShell } from "@/features/preparation";
import { useAppForm } from "@/hooks/useAppForm";
import { Button, buttonClasses } from "@/ui/Button";
import { ApplicationIntakeForm } from "../components/ApplicationIntakeForm";
import { useApplicationIntakeSubmission } from "../hooks/useApplicationIntakeSubmission";
import {
  emptyApplicationIntake,
  intakeFromFields,
  isJobTextWithinBudget,
  type ApplicationIntakeFields,
} from "../model/applicationIntake";

const INTAKE_FORM_ID = "application-intake-form";

export const NewApplicationPage = () => {
  const navigate = useNavigate();
  const form = useAppForm<ApplicationIntakeFields>({ defaultValues: emptyApplicationIntake });
  /* `watch()` rather than `useWatch`: without a field name `useWatch` reports every value
     as optional, which is not what this form holds - it is registered from
     `emptyApplicationIntake`, so every field is a string from the first render. The
     intake is derived from those values on each render rather than memoised, because
     `watch()` returns a fresh object every time and the memo could never hit. */
  const fields = form.watch();
  const currentIntake = intakeFromFields(fields);

  const submission = useApplicationIntakeSubmission({
    currentIntake,
    onCreated: (result) => {
      void navigate(routePaths.application(result.applicationId), {
        replace: true,
        state: {
          createdApplication: { analysisProblem: result.analysisProblem, analysisQueued: result.analysisQueued },
        },
      });
    },
  });

  const submit = form.handleSubmit((submittedFields) => submission.submit(intakeFromFields(submittedFields)));
  const createAnyway = form.handleSubmit((submittedFields) =>
    submission.submit(intakeFromFields(submittedFields), true),
  );

  return (
    /* The first step, and the only one with no Application to read its position from - the
       record it creates does not exist yet, so the shell marks the stage this screen says
       it is. The spine carries the way back to the board, so the trail that used to sit
       above it is gone with the ones the other three steps drew. */
    <WizardStepShell
      description="הזנת פרטי המשרה יוצרת תצלום מקור קבוע ומתחילה ניתוח התאמה מול העובדות הקנוניות."
      stage="intake"
    >
      {/* The wizard frame carries the spine; the single-column form takes a shorter reading
          measure inside it so long fields remain easy to scan. */}
      <div className="mx-auto max-w-3xl">
        <ApplicationIntakeForm
          duplicates={submission.duplicateMatches}
          error={submission.error}
          errors={form.formState.errors}
          formId={INTAKE_FORM_ID}
          isStale={submission.isStale}
          jobText={fields.job_text}
          onInputChanged={submission.resetSettledResult}
          onSubmit={submit}
          register={form.register}
        />
      </div>
      <CommitBar
        back={
          <Link className={buttonClasses("ghost")} to={boardPath()}>
            <ArrowRight aria-hidden="true" className="size-4" />
            חזרה ללוח המועמדויות
          </Link>
        }
        label={NEXT_STEP_LABEL}
        primary={
          submission.duplicateMatches === null ? (
            <Button
              disabled={!isJobTextWithinBudget(fields.job_text)}
              form={INTAKE_FORM_ID}
              pending={submission.isSubmitting}
              pendingLabel="בודק כפילויות…"
              type="submit"
            >
              <Sparkles aria-hidden="true" className="size-4" />
              יצירת מועמדות
            </Button>
          ) : (
            <Button onClick={() => void createAnyway()} pending={submission.isSubmitting} pendingLabel="יוצר מועמדות…">
              יצירת מועמדות נוספת
            </Button>
          )
        }
      >
        <p className="text-support leading-6 text-cv-text-muted">
          {submission.duplicateMatches === null
            ? "יצירת המועמדות תשמור את תצלום המשרה ותתחיל את הניתוח."
            : "נדרש אישור מפורש כדי לשמור מועמדות חדשה לצד המועמדויות הדומות."}
        </p>
      </CommitBar>
    </WizardStepShell>
  );
};
