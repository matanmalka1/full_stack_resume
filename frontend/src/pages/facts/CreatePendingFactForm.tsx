import { useMutation, useQueryClient } from "@tanstack/react-query";

import { createPendingFact, factsQueryPrefix } from "../../api/facts";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { defaultFactSource, FactFields, type FactFormFields, parseFactTags } from "./FactFields";

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
  const form = useAppForm<FactFormFields>({
    defaultValues: {
      english: "",
      hebrew: "",
      meaning: "",
      provenance: "",
      source: defaultFactSource(profile),
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
    mutationFn: (fields: FactFormFields) =>
      createPendingFact({
        source: fields.source,
        meaning: fields.meaning.trim(),
        renderings: {
          en: fields.english.trim(),
          ...(fields.hebrew.trim() === "" ? {} : { he: fields.hebrew.trim() }),
        },
        tags: parseFactTags(fields.tags),
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

      <FactFields errors={errors} includeHebrew includeStyle register={register} twoColumn />
      <Button className="lg:col-span-2" pending={create.isPending} pendingLabel="יוצר…" type="submit">
        יצירת עובדה ממתינה
      </Button>
    </form>
  );
};
