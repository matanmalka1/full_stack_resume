import { type ReactNode, useEffect } from "react";

import { Button } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { useAppForm } from "@/hooks/useAppForm";
import { useCreatePendingFact } from "../api/mutations";
import { useFactPool } from "../api/queries";
import { emptyFactForm, type FactFormFields, parseFactTags } from "../model/factForm";
import {
  FactCoreFields,
  FactHebrewRenderingField,
  FactProvenanceField,
  FactSourceField,
  FactStyleField,
  FactTagsField,
} from "./FactFormFieldset";

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
   canonical without a separate, explicit confirmation. The Hebrew rendering is optional
   because the English one is what the CV is built from.

   It is a modal rather than a disclosure on the page. Eight fields unfolding inline
   pushed the fact pool and the selected fact - the two things the screen exists to show -
   below the fold every time someone opened it, and a half-filled form stayed on screen
   competing with the list for the same column. As a dialog the writing task owns the
   screen while it is open and gives the whole page back when it closes. The fields are
   drawn one size down (`cv-fields-compact`): a form of eight controls at full field size
   outgrows a dialog, and none of these values is longer than a sentence.

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
    getValues,
    register,
    reset,
    setValue,
    watch,
  } = form;
  /* Already cached by the pool this dialog was opened from; no request of its own. */
  const pool = useFactPool();
  const chosen = parseFactTags(watch("tags"));
  const poolTags = [...new Set((pool.data?.entries ?? []).flatMap(({ fact }) => fact.tags))];
  const knownTags = poolTags
    .filter((tag) => !chosen.includes(tag))
    /* Sorting a list this expression just built, not a caller's array. */
    // oxlint-disable-next-line unicorn/no-array-sort
    .sort((first, second) => first.localeCompare(second));
  /* An empty store has no vocabulary to choose from, and a tag is required, so the first
     facts fall back to typing their tags. The picker takes over as soon as one exists. */
  const hasVocabulary = poolTags.length > 0;

  const writeTags = (tags: string[]) => setValue("tags", tags.join(", "), { shouldDirty: true, shouldValidate: true });
  const create = useCreatePendingFact((factId) => {
    reset();
    onCreated(factId);
    onClose();
  });

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
      provenance: fields.provenance.trim(),
      resume_style: fields.style,
      ...(replaces === undefined ? {} : { replaces }),
      reason,
    });

  return (
    <Dialog
      footer={
        <>
          <Button onClick={onClose} variant="secondary">
            ביטול
          </Button>
          <Button form={formId} pending={create.isPending} pendingLabel="יוצר…" type="submit">
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
      {intro}

      <form
        className="cv-fields-compact mt-4 grid gap-3 sm:grid-cols-2"
        id={formId}
        onSubmit={form.handleSubmit(submit)}
      >
        {create.error === null ? null : (
          <ErrorCallout
            className="sm:col-span-2"
            error={create.error}
            fallbackDetail="מקור הידע לא השתנה ואפשר לנסות שוב."
            fallbackTitle="לא ניתן ליצור את העובדה"
          />
        )}

        <FactSourceField register={register} />
        <FactStyleField register={register} />
        <FactCoreFields className="sm:col-span-2" errors={errors} register={register} />
        <FactHebrewRenderingField register={register} />
        <FactTagsField
          errors={errors}
          picker={
            hasVocabulary
              ? {
                  chosen,
                  known: knownTags,
                  onAdd: (tag) => writeTags([...parseFactTags(getValues("tags")), tag]),
                  onRemove: (tag) => writeTags(parseFactTags(getValues("tags")).filter((current) => current !== tag)),
                }
              : undefined
          }
          register={register}
        />
        <FactProvenanceField errors={errors} register={register} />
      </form>
    </Dialog>
  );
};
