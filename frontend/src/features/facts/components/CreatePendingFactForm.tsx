import { ErrorCallout } from "@/ui/ErrorCallout";
import { useAppForm } from "@/hooks/useAppForm";
import { Button } from "@/ui/Button";
import { useCreatePendingFact } from "../api/mutations";
import { emptyFactForm, type FactFormFields, parseFactTags } from "../model/factForm";
import {
  FactCoreFields,
  FactHebrewRenderingField,
  FactProvenanceField,
  FactSourceField,
  FactStyleField,
  FactTagsField,
} from "./FactFormFieldset";

interface CreatePendingFactFormProps {
  onCreated: (factId: string) => void;
  profile: string | null;
}

/* A new fact entered by hand, which always starts pending: nothing typed here becomes
   canonical without a separate, explicit confirmation. The Hebrew rendering is optional
   because the English one is what the CV is built from. */
export const CreatePendingFactForm = ({ onCreated, profile }: CreatePendingFactFormProps) => {
  const form = useAppForm<FactFormFields>({ defaultValues: emptyFactForm(profile) });
  const {
    formState: { errors },
    register,
    reset,
  } = form;
  const create = useCreatePendingFact((factId) => {
    reset();
    onCreated(factId);
  });

  const submit = (fields: FactFormFields) =>
    create.mutate({
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
    });

  return (
    <form className="mt-4 grid gap-3 lg:grid-cols-2" onSubmit={form.handleSubmit(submit)}>
      {create.error === null ? null : (
        <ErrorCallout
          className="lg:col-span-2"
          error={create.error}
          fallbackDetail="מקור הידע לא השתנה ואפשר לנסות שוב."
          fallbackTitle="לא ניתן ליצור את העובדה"
        />
      )}

      <FactSourceField register={register} />
      <FactStyleField register={register} />
      <FactCoreFields className="lg:col-span-2" errors={errors} register={register} />
      <FactHebrewRenderingField register={register} />
      <FactTagsField errors={errors} register={register} />
      <FactProvenanceField errors={errors} register={register} />

      <Button className="lg:col-span-2" pending={create.isPending} pendingLabel="יוצר…" type="submit">
        יצירת עובדה ממתינה
      </Button>
    </form>
  );
};
