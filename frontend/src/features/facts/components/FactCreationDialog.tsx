import { type ReactNode, useEffect } from "react";

import { Button } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { useAppForm } from "@/hooks/useAppForm";
import { useServerFieldErrors } from "@/hooks/useServerFieldErrors";
import { useCreatePendingFact } from "../api/mutations";
import { emptyFactForm, type FactFormFields, parseFactTags } from "../model/factForm";
import {
  FactEnglishField,
  FactHebrewRenderingField,
  FactMeaningField,
  FactSourceField,
  FactStyleField,
  FactTagsField,
} from "./FactFormFieldset";

/* The API's names for the fields this form shows errors under. */
const serverFields = {
  meaning: "meaning",
  renderings: "english",
  en: "english",
  tags: "tags",
} as const satisfies Record<string, keyof FactFormFields>;

interface FactCreationDialogProps {
  formId: string;
  headingId: string;
  initialValues?: FactFormFields;
  intro?: ReactNode;
  onClose: () => void;
  onCreated: (factId: string) => void;
  open: boolean;
  reason: string;
  replaces?: string;
  submitLabel: string;
  title: string;
}

/* A new fact entered by hand, which always starts pending: nothing typed here becomes
   canonical without a separate, explicit promotion. The Hebrew rendering is optional
   because the English one is what the CV is built from.

   Laid out as the design draws it - the kind as a row of pills, then the fields in pairs:
   the two wordings side by side, the tags beside the knowledge file. The design has no
   place for the fact's meaning, but the store requires it and never infers it, so it
   closes the form. A phone stacks every pair and
   ends the sheet on its one command; its X is the way out.

   The same dialog serves the correction of a canonical fact - same command, same pending
   result, only seeded with the original's values and carrying a `replaces` link - so the
   two writes cannot drift apart in behavior or in wording. */
export const FactCreationDialog = ({
  formId,
  headingId,
  initialValues,
  intro,
  onClose,
  onCreated,
  open,
  reason,
  replaces,
  submitLabel,
  title,
}: FactCreationDialogProps) => {
  const form = useAppForm<FactFormFields>({ defaultValues: initialValues ?? emptyFactForm(null) });
  const {
    formState: { errors },
    register,
    reset,
    setError,
    setValue,
    watch,
  } = form;
  const create = useCreatePendingFact((factId) => {
    reset();
    onCreated(factId);
    onClose();
  });

  const inlineFields = useServerFieldErrors(create.error, setError, serverFields);

  /* Reopening starts from the seed values again rather than from whatever was abandoned
     last time, and a failure from the previous attempt does not greet the next one. */
  useEffect(() => {
    if (open) {
      create.reset();
      reset(initialValues ?? emptyFactForm(null));
    }
    /* Seeded once per opening: re-seeding on every render would erase what is being typed. */
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = (fields: FactFormFields) =>
    create.mutate({
      source: fields.source,
      meaning: fields.meaning.trim(),
      renderings: {
        en: fields.english.trim(),
        ...(fields.hebrew.trim() === "" ? {} : { he: fields.hebrew.trim() }),
      },
      tags: parseFactTags(fields.tags),
      resume_style: fields.style,
      ...(replaces === undefined ? {} : { replaces }),
      reason,
    });

  return (
    <Dialog
      footer={
        <>
          <Button className="max-lg:hidden" onClick={onClose} size="default" variant="secondary">
            ביטול
          </Button>
          <Button
            className="max-lg:min-h-13 max-lg:rounded-control-lg"
            form={formId}
            pending={create.isPending}
            pendingLabel="יוצר…"
            size="default"
            type="submit"
          >
            {submitLabel}
          </Button>
        </>
      }
      headingId={headingId}
      onClose={onClose}
      open={open}
      size="wide"
      title={title}
    >
      {intro === undefined ? null : <div className="mb-4">{intro}</div>}

      <form className="flex flex-col gap-4.5" id={formId} onSubmit={form.handleSubmit(submit)}>
        <FactStyleField onChange={(style) => setValue("style", style, { shouldDirty: true })} value={watch("style")} />
        <div className="grid gap-4 lg:grid-cols-2 lg:gap-3.5">
          <FactHebrewRenderingField register={register} />
          <FactEnglishField errors={errors} register={register} />
          <FactTagsField errors={errors} register={register} />
          <FactSourceField register={register} />
          <FactMeaningField errors={errors} register={register} />
        </div>
        {create.error === null ? null : (
          <ErrorCallout
            error={create.error}
            fallbackDetail="הפרטים שהוזנו נשארו בטופס. אפשר לנסות שוב."
            inlineFields={inlineFields}
            title="העובדה לא נוצרה"
          />
        )}
      </form>
    </Dialog>
  );
};
