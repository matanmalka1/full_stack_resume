import type { UseFormRegisterReturn } from "react-hook-form";

import { Field } from "@/ui/Field";
import { Input } from "@/ui/Input";
import { isoFromLocalDateTimeInput } from "@/utils/isoFromLocalDateTimeInput";

/* The rules every submission form registers its `submittedAt` with. A value that passes
   them always converts, so the mutation's own conversion never meets an invalid date. */
export const submittedAtRules = {
  required: "יש להזין מועד הגשה.",
  validate: (value: string) => isoFromLocalDateTimeInput(value) !== null || "יש להזין מועד הגשה תקין.",
};

interface SubmittedAtFieldProps {
  error: string | undefined;
  registration: UseFormRegisterReturn;
}

/* When a submission happened, for both ways one is recorded: the internal recording of a
   Ready document and an external submission made outside the system. */
export const SubmittedAtField = ({ error, registration }: SubmittedAtFieldProps) => (
  <Field error={error} label="מועד ההגשה">
    {(control) => <Input {...control} {...registration} required type="datetime-local" />}
  </Field>
);
