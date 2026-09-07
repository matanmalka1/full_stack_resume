import { Sparkles } from "lucide-react";
import type { FormEventHandler } from "react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";

import type { DuplicateMatch } from "@/api/contracts";
import { ActionBar } from "@/ui/ActionBar";
import { Button } from "@/ui/Button";
import { surfaceClasses } from "@/ui/Surface";
import { isJobTextWithinBudget, type ApplicationIntakeFields } from "../model/applicationIntake";
import { DuplicateChoices } from "./DuplicateChoices";
import { IntakeFeedback } from "./IntakeFeedback";
import { JobDetailsFields } from "./JobDetailsFields";
import { JobTextField } from "./JobTextField";

interface ApplicationIntakeFormProps {
  duplicates: DuplicateMatch[] | null;
  error: Error | null;
  errors: FieldErrors<ApplicationIntakeFields>;
  isStale: boolean;
  isSubmitting: boolean;
  jobText: string;
  onCreateAnyway: () => void;
  onInputChanged: () => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
  register: UseFormRegister<ApplicationIntakeFields>;
}

export const ApplicationIntakeForm = ({
  duplicates,
  error,
  errors,
  isStale,
  isSubmitting,
  jobText,
  onCreateAnyway,
  onInputChanged,
  onSubmit,
  register,
}: ApplicationIntakeFormProps) => (
  <form
    className={surfaceClasses("flex flex-col gap-6 bg-cv-surface p-5 shadow-surface sm:p-7")}
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
    {duplicates === null ? null : (
      <DuplicateChoices matches={duplicates} onCreateAnyway={onCreateAnyway} pending={isSubmitting} />
    )}
    <IntakeFeedback error={error} isStale={isStale} />
    {duplicates === null ? (
      <ActionBar
        align="start"
        primary={
          <Button
            disabled={!isJobTextWithinBudget(jobText)}
            pending={isSubmitting}
            pendingLabel="בודק כפילויות…"
            type="submit"
          >
            <Sparkles aria-hidden="true" className="size-4" />
            יצירת מועמדות
          </Button>
        }
      />
    ) : null}
  </form>
);
