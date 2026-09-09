import type { FormEventHandler } from "react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";

import type { DuplicateMatch } from "@/api/contracts";
import { surfaceClasses } from "@/ui/surface";
import { type ApplicationIntakeFields } from "../model/applicationIntake";
import { DuplicateChoices } from "./DuplicateChoices";
import { IntakeFeedback } from "./IntakeFeedback";
import { JobDetailsFields } from "./JobDetailsFields";
import { JobTextField } from "./JobTextField";

interface ApplicationIntakeFormProps {
  duplicates: DuplicateMatch[] | null;
  error: Error | null;
  errors: FieldErrors<ApplicationIntakeFields>;
  isStale: boolean;
  formId: string;
  jobText: string;
  onInputChanged: () => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
  register: UseFormRegister<ApplicationIntakeFields>;
}

export const ApplicationIntakeForm = ({
  duplicates,
  error,
  errors,
  formId,
  isStale,
  jobText,
  onInputChanged,
  onSubmit,
  register,
}: ApplicationIntakeFormProps) => (
  <form
    className={surfaceClasses("flex flex-col gap-6 bg-cv-surface p-5 shadow-surface sm:p-7")}
    id={formId}
    noValidate
    onSubmit={onSubmit}
  >
    <JobDetailsFields errors={errors} onInputChanged={onInputChanged} register={register} />
    <JobTextField
      error={errors.job_text?.message}
      jobText={jobText}
      onInputChanged={onInputChanged}
      register={register}
    />
    {duplicates === null ? null : <DuplicateChoices matches={duplicates} />}
    <IntakeFeedback error={error} isStale={isStale} />
  </form>
);
