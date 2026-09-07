import type { FieldErrors, UseFormRegister } from "react-hook-form";

import { Field } from "@/ui/Field";
import { Select } from "@/ui/Select";
import { Input, Textarea } from "@/ui/Input";
import { factFieldRules, type FactFormFields } from "../model/factForm";
import { factSourceLabels, factStyleLabels } from "../model/factLabels";

interface FactFormControl {
  errors: FieldErrors<FactFormFields>;
  register: UseFormRegister<FactFormFields>;
}

/* The fields every fact write shares - what the fact means, how it is worded, how it is
   tagged, and where it came from. The two forms differ only in which optional fields
   they add around these, so those are separate components below rather than flags on
   this one. */
export const FactCoreFields = ({
  className,
  englishHint,
  errors,
  register,
  showEnglish = true,
}: FactFormControl & { className?: string; englishHint?: string; showEnglish?: boolean }) => (
  <>
    <Field className={className} error={errors.meaning?.message} label="משמעות">
      {(control) => <Textarea {...control} {...register("meaning", factFieldRules.meaning)} dir="auto" />}
    </Field>
    {showEnglish ? (
      <Field error={errors.english?.message} hint={englishHint} label="ניסוח באנגלית">
        {(control) => <Textarea {...control} {...register("english", factFieldRules.english)} dir="ltr" />}
      </Field>
    ) : null}
  </>
);

export const FactTagsField = ({ errors, register }: FactFormControl) => (
  <Field error={errors.tags?.message} hint="יש להפריד תגיות בפסיקים." label="תגיות">
    {(control) => <Input {...control} {...register("tags", factFieldRules.tags)} />}
  </Field>
);

export const FactProvenanceField = ({ errors, register }: FactFormControl) => (
  <Field error={errors.provenance?.message} label="מקור ואימות העובדה">
    {(control) => <Textarea {...control} {...register("provenance", factFieldRules.provenance)} dir="auto" />}
  </Field>
);

export const FactSourceField = ({ register }: Pick<FactFormControl, "register">) => (
  <Field label="מקור הידע">
    {(control) => (
      <Select {...control} {...register("source")}>
        {Object.entries(factSourceLabels).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </Select>
    )}
  </Field>
);

export const FactStyleField = ({ register }: Pick<FactFormControl, "register">) => (
  <Field label="סוג הצגה">
    {(control) => (
      <Select {...control} {...register("style")}>
        {Object.entries(factStyleLabels).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </Select>
    )}
  </Field>
);

export const FactHebrewRenderingField = ({ register }: Pick<FactFormControl, "register">) => (
  <Field label="ניסוח בעברית" optional>
    {(control) => <Textarea {...control} {...register("hebrew")} />}
  </Field>
);
