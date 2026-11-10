import { Sparkle, X } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useIsPhone } from "@/ui/useIsPhone";
import { useAiAvailability } from "@/features/settings";
import { routePaths } from "@/navigation/routePaths";
import { isJobTextWithinBudget } from "@/features/application-detail";
import { workflowStageLabels, workflowStages } from "@/features/preparation";
import { useAppForm } from "@/hooks/useAppForm";
import { Button, buttonClasses } from "@/ui/Button";
import { LiveRegion } from "@/ui/LiveRegion";
import { PhoneActionBar } from "@/ui/PhoneActionBar";
import { cx } from "@/ui/cx";
import { ApplicationIntakeForm } from "../components/ApplicationIntakeForm";
import { IntakeDraftStatus } from "../components/IntakeDraftStatus";
import { useApplicationIntakeSubmission } from "../hooks/useApplicationIntakeSubmission";
import { readApplicationIntakeDraft, useApplicationIntakeDraft } from "../hooks/useApplicationIntakeDraft";
import { emptyApplicationIntake, intakeFromFields, type ApplicationIntakeFields } from "../model/applicationIntake";

const INTAKE_FORM_ID = "application-intake-form";

/* A phone's stepper names the first three stages in a word each; the fourth does not fit
   beside them and is left to the wide screen. */
const phoneStageNames = ["מודעה", "ניתוח", "טיוטה"];

/* Where the new job sits in the flow, before there is a record to read a position from:
   the first of the stages, numbered, the rest ahead of it. Decorative - the heading
   right above it says which step this is. */
const IntakeStepper = () => (
  <ol aria-hidden="true" className="flex items-center gap-2.5 text-label max-lg:gap-2 max-lg:text-support">
    {workflowStages.map((stage, index) => {
      const current = index === 0;
      const phoneName = phoneStageNames[index];
      return (
        <Fragment key={stage}>
          {index === 0 ? null : (
            <li className={cx("h-px min-w-3 flex-1 bg-cv-border-soft", phoneName === undefined && "max-lg:hidden")} />
          )}
          <li
            className={cx(
              "flex shrink-0 items-center gap-2 max-lg:gap-1.5",
              current ? "font-bold text-cv-text" : "text-cv-text-muted",
              phoneName === undefined && "max-lg:hidden",
            )}
          >
            <span
              className={cx(
                "flex size-6 items-center justify-center rounded-pill text-caption max-lg:size-5.5",
                current ? "bg-cv-accent text-cv-on-accent" : "border-[1.5px] border-cv-border-strong",
              )}
            >
              {index + 1}
            </span>
            <span className="max-lg:hidden">{workflowStageLabels[stage]}</span>
            <span className="lg:hidden">{phoneName}</span>
          </li>
        </Fragment>
      );
    })}
  </ol>
);

/* The first step of the flow: paste the posting, name the job, and save it - which
   creates the Application and, where a provider is set, starts its analysis. The screen
   then moves to the analysis step, where the run is reported. */
export const NewApplicationPage = () => {
  const navigate = useNavigate();
  const isPhone = useIsPhone();
  const [recoveredDraft] = useState(readApplicationIntakeDraft);
  const form = useAppForm<ApplicationIntakeFields>({ defaultValues: recoveredDraft ?? emptyApplicationIntake });
  /* `watch()` rather than `useWatch`: without a field name `useWatch` reports every value
     as optional, which is not what this form holds - it is registered from
     `emptyApplicationIntake`, so every field is a string from the first render. The
     intake is derived from those values on each render rather than memoised, because
     `watch()` returns a fresh object every time and the memo could never hit. */
  const fields = form.watch();
  const currentIntake = intakeFromFields(fields);
  const intakeDraft = useApplicationIntakeDraft(fields, recoveredDraft !== null);
  /* Analysis is AI-only. Until the settings read settles, creation requests it as before;
     once Settings say there is no provider, the screen says so and creation does not
     queue a run the server would only refuse. */
  const analysisUnavailable = useAiAvailability() === "missing";

  const submission = useApplicationIntakeSubmission({
    analysisAvailable: !analysisUnavailable,
    currentIntake,
    onCreated: (result, createdInputIsCurrent) => {
      if (createdInputIsCurrent) intakeDraft.clearDraft();
      void navigate(routePaths.analysis(result.applicationId), {
        replace: true,
        state: {
          createdApplication: {
            analysisProblem: result.analysisProblem,
            analysisSkipped: result.analysisSkipped,
            operationId: result.operation?.id ?? null,
          },
        },
      });
    },
  });

  useEffect(() => {
    if (submission.fieldErrors === null) return;

    const entries = Object.entries(submission.fieldErrors) as [keyof ApplicationIntakeFields, string][];
    for (const [field, message] of entries) {
      form.setError(field, { type: "server", message });
    }
    const firstInvalidField = entries[0]?.[0];
    if (firstInvalidField !== undefined) form.setFocus(firstInvalidField);
  }, [form, submission.fieldErrors]);

  const inlineFields = new Set(Object.keys(submission.fieldErrors ?? {}));

  const submit = form.handleSubmit((submittedFields) => submission.submit(intakeFromFields(submittedFields)));
  const createAnyway = form.handleSubmit((submittedFields) =>
    submission.submit(intakeFromFields(submittedFields), true),
  );
  const onInputChanged = (field: keyof ApplicationIntakeFields) => {
    intakeDraft.updateDraft(form.getValues());
    form.clearErrors(field);
    submission.resetSettledResult();
  };
  const onPaste = (text: string) => {
    form.setValue("job_text", text, { shouldDirty: true });
    onInputChanged("job_text");
  };

  const duplicates = submission.duplicateMatches;
  const primary =
    duplicates === null ? (
      <Button
        className="shadow-action"
        disabled={!isJobTextWithinBudget(fields.job_text)}
        form={INTAKE_FORM_ID}
        pending={submission.isSubmitting}
        pendingLabel="בודק כפילויות…"
        size="default"
        type="submit"
      >
        <Sparkle aria-hidden="true" className="size-icon-md" />
        {analysisUnavailable ? "שמירת המשרה" : "שמירה וניתוח המשרה"}
      </Button>
    ) : (
      <Button
        onClick={() => void createAnyway()}
        pending={submission.isSubmitting}
        pendingLabel="יוצר מועמדות…"
        size="default"
      >
        יצירת מועמדות נוספת
      </Button>
    );
  /* What the press will do, where it is not the obvious: no provider to analyze with, or
     a similar Application already on the board. */
  const note =
    duplicates !== null
      ? duplicates.length === 1
        ? "נמצאה מועמדות דומה. אפשר לפתוח אותה או לאשר יצירת מועמדות נוספת."
        : `נמצאו ${duplicates.length} מועמדויות דומות. אפשר לפתוח אחת מהן או לאשר יצירת מועמדות נוספת.`
      : analysisUnavailable
        ? "ניתוח המשרה דורש ספק AI, ועדיין לא הוגדר כזה. המשרה תישמר, והניתוח יהיה זמין אחרי הגדרתו במסך ההגדרות."
        : undefined;
  const noteLine =
    note === undefined ? null : (
      <LiveRegion className="text-support leading-relaxed text-cv-text-muted" visuallyHidden={false}>
        {note}
      </LiveRegion>
    );

  const status = <IntakeDraftStatus status={intakeDraft.status} />;

  return (
    <section
      aria-labelledby="route-heading"
      className="page-frame flex flex-col gap-5 [--page-measure:51.25rem] max-lg:gap-4.5"
    >
      {/* A phone's header: the way out as a close mark - nothing has been created yet, so
          leaving is cancelling - and where the draft stands. */}
      {isPhone ? (
        <div className="-ms-2 -mt-1.5 flex items-center justify-between gap-3">
          <Link
            aria-label="ביטול וחזרה לקורות החיים"
            className="flex size-11 shrink-0 items-center justify-center rounded-control text-cv-text"
            to={routePaths.home()}
          >
            <X aria-hidden="true" className="size-5.5" />
          </Link>
          {status}
        </div>
      ) : null}

      <div>
        <h1
          className="text-title font-extrabold tracking-tight text-cv-text lg:text-display"
          data-route-heading
          id="route-heading"
          tabIndex={-1}
        >
          משרה חדשה
        </h1>
        <div className="mt-1.5 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
          <p className="text-label text-cv-text-muted lg:text-body">מדביקים את המודעה, והניתוח יחלץ ממנה את הדרישות.</p>
          {isPhone ? null : status}
        </div>
      </div>

      <IntakeStepper />

      <ApplicationIntakeForm
        {...(isPhone
          ? {}
          : {
              actions: (
                <div className="flex flex-col gap-3">
                  {noteLine}
                  <div className="flex justify-end gap-2.5">
                    <Link className={buttonClasses("secondary", undefined, "default")} to={routePaths.home()}>
                      ביטול
                    </Link>
                    {primary}
                  </div>
                </div>
              ),
            })}
        duplicates={duplicates}
        error={submission.error}
        errors={form.formState.errors}
        formId={INTAKE_FORM_ID}
        inlineFields={inlineFields}
        isStale={submission.isStale}
        jobText={fields.job_text}
        onInputChanged={onInputChanged}
        onPaste={onPaste}
        onSubmit={submit}
        register={form.register}
      />

      {isPhone ? (
        <>
          {noteLine}
          <PhoneActionBar>{primary}</PhoneActionBar>
        </>
      ) : null}
    </section>
  );
};
