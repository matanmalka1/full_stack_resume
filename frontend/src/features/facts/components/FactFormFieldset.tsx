import type { FieldErrors, UseFormRegister } from "react-hook-form";

import { ChoiceChips } from "@/ui/ChoiceChips";
import { Field } from "@/ui/Field";
import { Select } from "@/ui/Select";
import { Input, Textarea } from "@/ui/Input";
import { factFieldRules, type FactFormFields } from "../model/factForm";
import { type FactStyle, factSourceLabels, factStyleLabels } from "../model/factLabels";

interface FactFormControl {
  errors: FieldErrors<FactFormFields>;
  register: UseFormRegister<FactFormFields>;
}

/* The fields every fact write shares - what the fact means and how it is worded in
   English. The draft editor's capture form takes them as a pair; the facts screen's own
   dialog lays each out where the design puts it, so they are also exported one by one. */
export const FactMeaningField = ({ className, errors, register }: FactFormControl & { className?: string }) => (
  <Field className={className} error={errors.meaning?.message} label="משמעות">
    {(control) => <Textarea {...control} {...register("meaning", factFieldRules.meaning)} dir="auto" />}
  </Field>
);

export const FactEnglishField = ({ errors, hint, register }: FactFormControl & { hint?: string }) => (
  <Field error={errors.english?.message} hint={hint} label="ניסוח באנגלית">
    {(control) => <Textarea {...control} {...register("english", factFieldRules.english)} dir="ltr" />}
  </Field>
);

export const FactCoreFields = ({
  className,
  englishHint,
  errors,
  register,
  showEnglish = true,
}: FactFormControl & { className?: string; englishHint?: string; showEnglish?: boolean }) => (
  <>
    <FactMeaningField className={className} errors={errors} register={register} />
    {showEnglish ? <FactEnglishField errors={errors} hint={englishHint} register={register} /> : null}
  </>
);

/* Tags are stored as one comma-separated value, typed as the design draws the field. */
export const FactTagsField = ({ errors, register }: FactFormControl) => (
  <Field error={errors.tags?.message} hint="יש להפריד תגיות בפסיקים." label="תגיות">
    {(control) => <Input {...control} {...register("tags", factFieldRules.tags)} placeholder="הוספת תגית…" />}
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

/* The order the design lists the kinds in: the common ones first, the rare ones after. */
const styleOrder: FactStyle[] = ["bullet", "paragraph", "item", "contact", "heading", "date"];

/* Six short answers, all visible at once, as radio pills - a select hid five of them
   behind a tap. Controlled rather than registered: the pills are `ChoiceChips`, and the
   form's value is what they set. */
export const FactStyleField = ({ onChange, value }: { onChange: (style: FactStyle) => void; value: FactStyle }) => (
  <ChoiceChips
    label="סוג הצגה"
    onChange={onChange}
    options={styleOrder.map((style) => ({ label: factStyleLabels[style], value: style }))}
    value={value}
  />
);

export const FactHebrewRenderingField = ({ register }: Pick<FactFormControl, "register">) => (
  <Field label="ניסוח בעברית" optional>
    {(control) => <Textarea {...control} {...register("hebrew")} />}
  </Field>
);
