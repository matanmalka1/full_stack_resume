import { useNavigate, useSearchParams } from "react-router-dom";

import { routePaths } from "@/app/routePaths";
import { PreparationWorkflowSteps } from "@/features/preparation";
import { Breadcrumbs } from "@/ui/Breadcrumbs";
import { PageShell } from "@/ui/PageShell";
import { useAppForm } from "@/hooks/useAppForm";
import { paramsFromQuery, queryFromParams } from "@/features/application-list";
import { ApplicationIntakeForm } from "../components/ApplicationIntakeForm";
import { useApplicationIntakeSubmission } from "../hooks/useApplicationIntakeSubmission";
import { emptyApplicationIntake, intakeFromFields, type ApplicationIntakeFields } from "../model/applicationIntake";

export const NewApplicationPage = () => {
  const navigate = useNavigate();
  const [boardParams] = useSearchParams();
  const form = useAppForm<ApplicationIntakeFields>({ defaultValues: emptyApplicationIntake });
  /* `watch()` rather than `useWatch`: without a field name `useWatch` reports every value
     as optional, which is not what this form holds - it is registered from
     `emptyApplicationIntake`, so every field is a string from the first render. The
     intake is derived from those values on each render rather than memoised, because
     `watch()` returns a fresh object every time and the memo could never hit. */
  const fields = form.watch();
  const currentIntake = intakeFromFields(fields);
  const boardSearch = paramsFromQuery(queryFromParams(boardParams)).toString();
  const boardPath = boardSearch === "" ? routePaths.home : `${routePaths.home}?${boardSearch}`;

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
    <PageShell
      description="הזנת פרטי המשרה יוצרת תצלום מקור קבוע ומתחילה ניתוח התאמה מול העובדות הקנוניות."
      landmark={<PreparationWorkflowSteps stage="intake" />}
      navigation={<Breadcrumbs items={[{ label: "מועמדויות", to: boardPath }, { label: "משרה חדשה" }]} />}
      title="קליטת משרה חדשה"
    >
      {/* The page keeps the wide measure so the wizard spine spans the frame like every
          other step, while the form itself holds the shorter reading measure a single
          column of inputs wants - a text field stretched across the full frame is harder to
          scan, not easier. */}
      <div className="mx-auto max-w-3xl">
        <ApplicationIntakeForm
          duplicates={submission.duplicateMatches}
          error={submission.error}
          errors={form.formState.errors}
          isStale={submission.isStale}
          isSubmitting={submission.isSubmitting}
          jobText={fields.job_text}
          onCreateAnyway={() => void createAnyway()}
          onInputChanged={submission.resetSettledResult}
          onSubmit={submit}
          register={form.register}
        />
      </div>
    </PageShell>
  );
};
