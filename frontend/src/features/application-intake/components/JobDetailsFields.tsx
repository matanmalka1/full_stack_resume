import type { ReactNode } from "react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";

import { Field } from "@/ui/Field";
import { Input } from "@/ui/Input";
import { cx } from "@/ui/cx";
import { LABEL_MAX_CHARACTERS, SOURCE_URL_MAX_CHARACTERS, validateSourceUrl } from "@/features/application-detail";
import type { ApplicationIntakeFields } from "../model/applicationIntake";

interface JobDetailsFieldsProps {
  errors: FieldErrors<ApplicationIntakeFields>;
  onInputChanged: (field: keyof ApplicationIntakeFields) => void;
  register: UseFormRegister<ApplicationIntakeFields>;
}

/* The job's three names - who, what, where it was posted - as one group under its own
   legend. A phone sets company and role side by side over the link; a wide screen puts
   all three on one row. */
export const JobDetailsFields = ({ errors, onInputChanged, register }: JobDetailsFieldsProps) => (
  <fieldset className="flex min-w-0 flex-col gap-3">
    <legend className="mb-3 text-label font-bold text-cv-text max-lg:mb-2.5">פרטי המשרה</legend>
    <div className="grid grid-cols-2 gap-x-2.5 gap-y-3 lg:grid-cols-3 lg:gap-x-3.5">
      <DetailField error={errors.company?.message} label="חברה">
        {(control) => (
          <Input
            {...control}
            {...register("company", {
              onChange: () => onInputChanged("company"),
              validate: (value) => value.trim() !== "" || "יש להזין את שם החברה.",
            })}
            autoComplete="organization"
            className="rtl-placeholder"
            dir="auto"
            maxLength={LABEL_MAX_CHARACTERS}
            placeholder="שם החברה"
          />
        )}
      </DetailField>
      <DetailField error={errors.target_role?.message} label="תפקיד">
        {(control) => (
          <Input
            {...control}
            {...register("target_role", {
              onChange: () => onInputChanged("target_role"),
              validate: (value) => value.trim() !== "" || "יש להזין את תפקיד היעד.",
            })}
            className="rtl-placeholder"
            dir="auto"
            maxLength={LABEL_MAX_CHARACTERS}
            placeholder="שם התפקיד"
          />
        )}
      </DetailField>
      <DetailField className="max-lg:col-span-2" error={errors.source_url?.message} label="קישור למודעה (לא חובה)">
        {(control) => (
          <Input
            {...control}
            {...register("source_url", { onChange: () => onInputChanged("source_url"), validate: validateSourceUrl })}
            /* The empty field sits on the RTL edge with its neighbours; a typed address is
               still an LTR island. */
            className="ltr-island rtl-placeholder"
            dir="ltr"
            inputMode="url"
            maxLength={SOURCE_URL_MAX_CHARACTERS}
            placeholder={"\u2066https://\u2069"}
            type="url"
          />
        )}
      </DetailField>
    </div>
  </fieldset>
);

/* A field of the group: a quieter label than a standalone field's, since the legend above
   already names what the three are. The control's name and error wiring are `Field`'s. */
const DetailField = ({
  children,
  className,
  error,
  label,
}: {
  children: Parameters<typeof Field>[0]["children"];
  className?: string;
  error: string | undefined;
  label: ReactNode;
}) => (
  <Field
    className={cx("min-w-0 [&_label]:text-support [&_label]:font-medium [&_label]:text-cv-text-muted", className)}
    error={error}
    label={label}
  >
    {children}
  </Field>
);
