import type { FormEventHandler } from "react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";

import type { DuplicateMatch } from "@/api/contracts";
import { surfaceClasses } from "@/ui/surface";
import type { IntakeDraftStatus as DraftStatus } from "../hooks/useApplicationIntakeDraft";
import { type ApplicationIntakeFields } from "../model/applicationIntake";
import { DuplicateChoices } from "./DuplicateChoices";
import { IntakeDraftStatus } from "./IntakeDraftStatus";
import { IntakeFeedback } from "./IntakeFeedback";
import { JobDetailsFields } from "./JobDetailsFields";
import { JobTextField } from "./JobTextField";

interface ApplicationIntakeFormProps {
  duplicates: DuplicateMatch[] | null;
  draftStatus: DraftStatus;
  error: Error | null;
  errors: FieldErrors<ApplicationIntakeFields>;
  inlineFields: ReadonlySet<string>;
  isStale: boolean;
  formId: string;
  jobText: string;
  onInputChanged: (field: keyof ApplicationIntakeFields) => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
  register: UseFormRegister<ApplicationIntakeFields>;
}

/* On a phone the form is not one card: each group is its own card on the canvas
   (`intakeSectionClasses`), and the form around them stays flat. */
export const ApplicationIntakeForm = ({
  duplicates,
  draftStatus,
  error,
  errors,
  formId,
  inlineFields,
  isStale,
  jobText,
  onInputChanged,
  onSubmit,
  register,
}: ApplicationIntakeFormProps) => (
  <form
    className={surfaceClasses(
      "flex flex-col gap-6 bg-cv-surface p-5 shadow-surface sm:p-7 max-lg:gap-4 max-lg:border-0 max-lg:bg-transparent max-lg:p-0 max-lg:shadow-none",
    )}
    id={formId}
    noValidate
    onSubmit={onSubmit}
  >
    <IntakeDraftStatus status={draftStatus} />
    <JobDetailsFields errors={errors} onInputChanged={onInputChanged} register={register} />
    <JobTextField
      error={errors.job_text?.message}
      jobText={jobText}
      onInputChanged={onInputChanged}
      register={register}
    />
    {duplicates === null ? null : <DuplicateChoices matches={duplicates} />}
    <IntakeFeedback error={error} inlineFields={inlineFields} isStale={isStale} />
  </form>
);
