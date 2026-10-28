import { X } from "lucide-react";
import type { FieldErrors, UseFormRegister } from "react-hook-form";

import { cx } from "@/ui/cx";
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

/* Tags are stored as one comma-separated value, and that value is what the form submits
   either way. What differs is how it is filled.

   Where the caller knows the pool it hands over `picker`, and the field stops accepting
   free text: the tags in use are offered by name and the chosen ones sit above the
   select as removable chips. Typing them by hand was the thing that split one tag into
   two - `follow-up` and `followup` are both legal, both spellings survive validation, and
   nothing downstream can tell they were meant to be the same tag. The value itself is
   still the comma-separated string, registered on a hidden input so its rule keeps
   reporting through this field.

   The draft editor's capture form knows no pool and passes no picker, so it keeps the
   plain text field. */
interface FactTagPicker {
  chosen: string[];
  known: string[];
  onAdd: (tag: string) => void;
  onRemove: (tag: string) => void;
}

export const FactTagsField = ({ errors, picker, register }: FactFormControl & { picker?: FactTagPicker }) => (
  <Field
    error={errors.tags?.message}
    hint={picker === undefined ? "יש להפריד תגיות בפסיקים." : "בחירה מתוך התגיות הקיימות במאגר."}
    label="תגיות"
  >
    {(control) =>
      picker === undefined ? (
        <Input {...control} {...register("tags", factFieldRules.tags)} />
      ) : (
        <div className="flex flex-col gap-2">
          <input type="hidden" {...register("tags", factFieldRules.tags)} />
          {picker.chosen.length === 0 ? null : (
            <ul className="flex flex-wrap items-center gap-1.5">
              {picker.chosen.map((tag) => (
                <li key={tag}>
                  <button
                    aria-label={`הסרת התגית ${tag}`}
                    className="inline-flex items-center gap-1 rounded-pill bg-cv-accent-soft px-2.5 py-1 text-support text-cv-accent transition-colors hover:bg-cv-accent hover:text-cv-on-accent"
                    onClick={() => picker.onRemove(tag)}
                    type="button"
                  >
                    <span dir="auto">{tag}</span>
                    <X aria-hidden="true" className="size-icon-sm" />
                  </button>
                </li>
              ))}
            </ul>
          )}
          {/* An action rather than a value: the select is bound to the empty option, so it
              returns to its own label after every pick and a tag removed above can be
              chosen again. */}
          <Select
            {...control}
            disabled={picker.known.length === 0}
            onChange={(event) => {
              if (event.target.value !== "") {
                picker.onAdd(event.target.value);
              }
            }}
            value=""
          >
            <option value="">{picker.known.length === 0 ? "אין תגיות נוספות במאגר" : "הוספת תגית…"}</option>
            {picker.known.map((tag) => (
              <option key={tag} value={tag}>
                {tag}
              </option>
            ))}
          </Select>
        </div>
      )
    }
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

/* Six short answers, all visible at once: native radios in a fieldset, drawn as chips.
   A select hid five of them behind a tap, which on a phone opened the system picker for a
   choice that fits on two lines. The radios are registered under the same field, so the
   value submitted is unchanged. */
export const FactStyleField = ({ className, register }: Pick<FactFormControl, "register"> & { className?: string }) => (
  <fieldset className={cx("flex min-w-0 flex-col gap-1.5", className)}>
    <legend className="mb-1.5 text-support font-medium text-cv-text">סוג הצגה</legend>
    <div className="flex flex-wrap gap-2">
      {Object.entries(factStyleLabels).map(([value, label]) => (
        <label
          className="inline-flex min-h-11 cursor-pointer items-center rounded-pill border border-cv-border bg-cv-surface px-4 text-support font-semibold text-cv-text transition-colors hover:border-cv-border-strong has-checked:border-cv-accent has-checked:bg-cv-accent has-checked:text-cv-on-accent has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-cv-focus"
          key={value}
        >
          <input className="sr-only" type="radio" value={value} {...register("style")} />
          {label}
        </label>
      ))}
    </div>
  </fieldset>
);

export const FactHebrewRenderingField = ({ register }: Pick<FactFormControl, "register">) => (
  <Field label="ניסוח בעברית" optional>
    {(control) => <Textarea {...control} {...register("hebrew")} />}
  </Field>
);
