import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createPendingFact, factsQueryPrefix } from "../../api/facts";
import type { CreateFactRequest } from "../../api/contracts";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Field } from "../../ui/Field";
import { Select } from "../../ui/Select";
import { TextArea, TextInput } from "../../ui/TextInput";

type FactSource = CreateFactRequest["source"];
type FactStyle = CreateFactRequest["resume_style"];

const sourceLabels: Record<FactSource, string> = {
  "common.md": "עובדות משותפות",
  "sales.md": "ניסיון במכירות",
  "development.md": "ניסיון בפיתוח",
  "situational_skills.md": "כישורים מצביים",
};

const styleLabels: Record<FactStyle, string> = {
  bullet: "שורת ניסיון",
  item: "פריט",
  paragraph: "פסקה",
  heading: "כותרת",
  date: "תאריך",
  contact: "פרט קשר",
};

interface CreatePendingFactFields {
  english: string;
  hebrew: string;
  meaning: string;
  provenance: string;
  source: FactSource;
  style: FactStyle;
  tags: string;
}

interface CreatePendingFactFormProps {
  onCreated: (factId: string) => void;
  profile: string | null;
}

/* A.4's "יצירת עובדה ממתינה חדשה" form, the one form on this editor that used to hold
   its seven fields as `useState` instead of `useAppForm` - every other form in the
   codebase validates and reports per-field errors through it, and this one now does
   too. */
export const CreatePendingFactForm = ({ onCreated, profile }: CreatePendingFactFormProps) => {
  const queryClient = useQueryClient();
  const form = useAppForm<CreatePendingFactFields>({
    defaultValues: {
      english: "",
      hebrew: "",
      meaning: "",
      provenance: "",
      source: profile === "development" ? "development.md" : "sales.md",
      style: "bullet",
      tags: "",
    },
  });
  const {
    formState: { errors },
    register,
    reset,
  } = form;

  const create = useMutation({
    mutationFn: (fields: CreatePendingFactFields) =>
      createPendingFact({
        source: fields.source,
        meaning: fields.meaning.trim(),
        renderings: {
          en: fields.english.trim(),
          ...(fields.hebrew.trim() === "" ? {} : { he: fields.hebrew.trim() }),
        },
        tags: fields.tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        provenance: fields.provenance.trim(),
        resume_style: fields.style,
        reason: "created from the contextual draft fact panel",
      }),
    onSuccess: (result) => {
      reset();
      void queryClient.invalidateQueries({ queryKey: factsQueryPrefix });
      onCreated(result.fact.fact_id);
    },
  });

  return (
    <form className="mt-4 grid gap-3 lg:grid-cols-2" onSubmit={form.handleSubmit((fields) => create.mutate(fields))}>
      {create.error === null ? null : (
        <ErrorCallout
          className="lg:col-span-2"
          error={create.error}
          fallbackDetail="מקור הידע לא השתנה ואפשר לנסות שוב."
          fallbackTitle="לא ניתן ליצור את העובדה"
        />
      )}

      <Field label="מקור הידע">
        {(control) => (
          <Select {...control} {...register("source")}>
            {Object.entries(sourceLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field label="סוג הצגה">
        {(control) => (
          <Select {...control} {...register("style")}>
            {Object.entries(styleLabels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field className="lg:col-span-2" error={errors.meaning?.message} label="משמעות">
        {(control) => (
          <TextArea
            {...control}
            {...register("meaning", { validate: (value) => value.trim() !== "" || "יש להזין משמעות." })}
            dir="auto"
          />
        )}
      </Field>
      <Field error={errors.english?.message} label="ניסוח באנגלית">
        {(control) => (
          <TextArea
            {...control}
            {...register("english", { validate: (value) => value.trim() !== "" || "יש להזין ניסוח באנגלית." })}
            dir="ltr"
          />
        )}
      </Field>
      <Field label="ניסוח בעברית (רשות)" optional>
        {(control) => <TextArea {...control} {...register("hebrew")} />}
      </Field>
      <Field error={errors.tags?.message} hint="יש להפריד תגיות בפסיקים." label="תגיות">
        {(control) => (
          <TextInput
            {...control}
            {...register("tags", {
              validate: (value) => value.split(",").some((tag) => tag.trim() !== "") || "יש להזין תגית אחת לפחות.",
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
      <Button className="lg:col-span-2" pending={create.isPending} pendingLabel="יוצר…" type="submit">
        יצירת עובדה ממתינה
      </Button>
    </form>
  );
};
