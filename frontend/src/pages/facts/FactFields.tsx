import type { FieldErrors, UseFormRegister } from "react-hook-form";

import { Field } from "../../ui/Field";
import { Select } from "../../ui/Select";
import { TextArea, TextInput } from "../../ui/TextInput";
import { factSourceLabels, factStyleLabels, type FactSource, type FactStyle } from "./factLabels";

export interface FactFormFields {
  english: string;
  hebrew: string;
  meaning: string;
  provenance: string;
  source: FactSource;
  style: FactStyle;
  tags: string;
}

export const defaultFactSource = (profile: string | null): FactSource =>
  profile === "development" ? "development.md" : "sales.md";

export const parseFactTags = (value: string): string[] =>
  value
    .split(",")
    .map((tag) => tag.trim())
    .filter(Boolean);

interface FactFieldsProps {
  englishHint?: string;
  errors: FieldErrors<FactFormFields>;
  includeHebrew?: boolean;
  includeStyle?: boolean;
  register: UseFormRegister<FactFormFields>;
  showEnglish?: boolean;
  twoColumn?: boolean;
}

export const FactFields = ({
  englishHint,
  errors,
  includeHebrew = false,
  includeStyle = false,
  register,
  showEnglish = true,
  twoColumn = false,
}: FactFieldsProps) => {
  const wideClassName = twoColumn ? "lg:col-span-2" : undefined;

  return (
    <>
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
      {includeStyle ? (
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
      ) : null}
      <Field className={wideClassName} error={errors.meaning?.message} label="משמעות">
        {(control) => (
          <TextArea
            {...control}
            {...register("meaning", { validate: (value) => value.trim() !== "" || "יש להזין משמעות." })}
            dir="auto"
          />
        )}
      </Field>
      {showEnglish ? (
        <Field error={errors.english?.message} hint={englishHint} label="ניסוח באנגלית">
          {(control) => (
            <TextArea
              {...control}
              {...register("english", { validate: (value) => value.trim() !== "" || "יש להזין ניסוח באנגלית." })}
              dir="ltr"
            />
          )}
        </Field>
      ) : null}
      {includeHebrew ? (
        <Field label="ניסוח בעברית" optional>
          {(control) => <TextArea {...control} {...register("hebrew")} />}
        </Field>
      ) : null}
      <Field error={errors.tags?.message} hint="יש להפריד תגיות בפסיקים." label="תגיות">
        {(control) => (
          <TextInput
            {...control}
            {...register("tags", {
              validate: (value) => parseFactTags(value).length > 0 || "יש להזין תגית אחת לפחות.",
            })}
          />
        )}
      </Field>
      <Field error={errors.provenance?.message} label="מקור ואימות העובדה">
        {(control) => (
          <TextArea
            {...control}
            {...register("provenance", { validate: (value) => value.trim() !== "" || "יש להזין מקור ואימות." })}
            dir="auto"
          />
        )}
      </Field>
    </>
  );
};
