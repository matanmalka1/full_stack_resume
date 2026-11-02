import type { FormEventHandler, ReactNode } from "react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";

import type { DuplicateMatch } from "@/api/contracts";
import { cardClasses } from "@/ui/surface";
import { type ApplicationIntakeFields } from "../model/applicationIntake";
import { DuplicateChoices } from "./DuplicateChoices";
import { IntakeFeedback } from "./IntakeFeedback";
import { JobDetailsFields } from "./JobDetailsFields";
import { JobTextField } from "./JobTextField";

interface ApplicationIntakeFormProps {
  /* The form's own commands, closing its card on a wide screen. A phone draws them in the
     bar on the screen's bottom edge instead, and passes nothing here. */
  actions?: ReactNode;
  duplicates: DuplicateMatch[] | null;
  error: Error | null;
  errors: FieldErrors<ApplicationIntakeFields>;
  inlineFields: ReadonlySet<string>;
  isStale: boolean;
  formId: string;
  jobText: string;
  onInputChanged: (field: keyof ApplicationIntakeFields) => void;
  onPaste: (text: string) => void;
  onSubmit: FormEventHandler<HTMLFormElement>;
  register: UseFormRegister<ApplicationIntakeFields>;
}

/* A wide screen holds the whole form in one card: the posting, its details, and the
   commands under a rule. On a phone each group is a card of its own on the canvas, and
   the form around them stays flat. */
export const ApplicationIntakeForm = ({
  actions,
  duplicates,
  error,
  errors,
  formId,
  inlineFields,
  isStale,
  jobText,
  onInputChanged,
  onPaste,
  onSubmit,
  register,
}: ApplicationIntakeFormProps) => (
  <form
    className={cardClasses(
      "flex flex-col gap-7 p-6 max-lg:gap-4.5 max-lg:border-0 max-lg:bg-transparent max-lg:p-0 max-lg:shadow-none",
    )}
    id={formId}
    noValidate
    onSubmit={onSubmit}
  >
    <div className="max-lg:rounded-surface max-lg:border max-lg:border-cv-hairline max-lg:bg-cv-surface max-lg:p-3.5 max-lg:shadow-surface">
      <JobTextField
        error={errors.job_text?.message}
        jobText={jobText}
        onInputChanged={onInputChanged}
        onPaste={onPaste}
        register={register}
      />
    </div>
    <div className="max-lg:rounded-surface max-lg:border max-lg:border-cv-hairline max-lg:bg-cv-surface max-lg:p-3.5 max-lg:shadow-surface">
      <JobDetailsFields errors={errors} onInputChanged={onInputChanged} register={register} />
    </div>
    {duplicates === null ? null : <DuplicateChoices matches={duplicates} />}
    <IntakeFeedback error={error} inlineFields={inlineFields} isStale={isStale} />
    {actions === undefined ? null : <div className="border-t border-cv-hairline pt-5">{actions}</div>}
  </form>
);
