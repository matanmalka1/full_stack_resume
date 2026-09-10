import { X } from "lucide-react";
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
