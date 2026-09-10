import { Briefcase, Building2, Link2, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";

import { Field } from "@/ui/Field";
import { FormSection } from "@/ui/FormSection";
import { Input } from "@/ui/Input";
import { LABEL_MAX_CHARACTERS, SOURCE_URL_MAX_CHARACTERS } from "@/features/applications";
import type { ApplicationIntakeFields } from "../model/applicationIntake";

const examplePlaceholder = (example: string) => `לדוגמה: \u2066${example}\u2069`;

const IconField = ({ children, icon: Icon }: { children: ReactNode; icon: LucideIcon }) => (
  <span className="relative block">
    <Icon
      aria-hidden="true"
      className="pointer-events-none absolute start-3.5 top-1/2 z-content-raised size-icon-md -translate-y-1/2 text-cv-text-muted"
    />
    {children}
  </span>
);

interface JobDetailsFieldsProps {
  errors: FieldErrors<ApplicationIntakeFields>;
  onInputChanged: () => void;
  register: UseFormRegister<ApplicationIntakeFields>;
}

export const JobDetailsFields = ({ errors, onInputChanged, register }: JobDetailsFieldsProps) => (
  <FormSection divided={false} title="פרטי המשרה">
    <div className="grid gap-4 md:grid-cols-2">
      <Field error={errors.company?.message} label="שם החברה">
        {(control) => (
          <IconField icon={Building2}>
            <Input
              {...control}
              {...register("company", {
                onChange: onInputChanged,
                validate: (value) => value.trim() !== "" || "יש להזין את שם החברה.",
              })}
              autoComplete="organization"
              className="rtl-placeholder ps-10"
              dir="auto"
              maxLength={LABEL_MAX_CHARACTERS}
              placeholder={examplePlaceholder("Stripe")}
            />
          </IconField>
        )}
      </Field>
      <Field error={errors.target_role?.message} label="תפקיד היעד">
        {(control) => (
          <IconField icon={Briefcase}>
            <Input
              {...control}
              {...register("target_role", {
                onChange: onInputChanged,
                validate: (value) => value.trim() !== "" || "יש להזין את תפקיד היעד.",
              })}
              className="rtl-placeholder ps-10"
              dir="auto"
              maxLength={LABEL_MAX_CHARACTERS}
              placeholder={examplePlaceholder("Senior Solutions Architect")}
            />
          </IconField>
        )}
      </Field>
    </div>
    <Field hint="נשמרת כתיעוד מקור בלבד, המערכת אינה פותחת את הכתובת או מייבאת ממנה טקסט." label="כתובת המשרה" optional>
      {(control) => (
        <IconField icon={Link2}>
          <Input
            {...control}
            {...register("source_url", { onChange: onInputChanged })}
            className="ltr-island ps-10"
            dir="ltr"
            inputMode="url"
            maxLength={SOURCE_URL_MAX_CHARACTERS}
            placeholder="https://company.example/careers/job"
            type="url"
          />
        </IconField>
      )}
    </Field>
  </FormSection>
);
