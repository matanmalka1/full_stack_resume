import { useEffect } from "react";

import type { Fact } from "@/api/contracts";
import {
  FactCoreFields,
  FactHebrewRenderingField,
  FactTagsField,
  type FactFormFields,
  parseFactTags,
} from "@/features/facts";
import { useAppForm } from "@/hooks/useAppForm";
import { Button } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { useEditGapFact } from "../../../api/gapQuestions";

const formFrom = (fact: Fact): FactFormFields => ({
  english: fact.renderings.en ?? "",
  hebrew: fact.renderings.he ?? "",
  meaning: fact.meaning,
  provenance: fact.provenance,
  source: fact.source as FactFormFields["source"],
  style: fact.resume_style as FactFormFields["style"],
  tags: fact.tags.join(", "),
});

/* §17 `edit_pending_fact`: what a drafted fact says, corrected before it is confirmed.
   Only meaning, renderings and tags are offered - the fact's source, style and provenance
   (the user's own answer) are not editable, so they are not fields here. The same field
   components as every other fact form, so the rules and wording cannot drift. */
export const GapFactEditDialog = ({
  applicationId,
  fact,
  headingId,
  onClose,
  open,
}: {
  applicationId: string;
  fact: Fact;
  headingId: string;
  onClose: () => void;
  open: boolean;
}) => {
  const form = useAppForm<FactFormFields>({ defaultValues: formFrom(fact) });
  const edit = useEditGapFact(applicationId, fact.fact_id, onClose);
  const formId = `${headingId}-form`;
  const fields = { errors: form.formState.errors, register: form.register };

  /* Each opening starts from the fact as it reads now, not from an abandoned edit. */
  useEffect(() => {
    if (open) {
      edit.reset();
      form.reset(formFrom(fact));
    }
    // oxlint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = (values: FactFormFields) =>
    edit.mutate({
      meaning: values.meaning.trim(),
      renderings: {
        en: values.english.trim(),
        ...(values.hebrew.trim() === "" ? {} : { he: values.hebrew.trim() }),
      },
      tags: parseFactTags(values.tags),
    });

  return (
    <Dialog
      footer={
        <>
          <Button onClick={onClose} variant="secondary">
            ביטול
          </Button>
          <Button form={formId} pending={edit.isPending} pendingLabel="שומר…" type="submit">
            שמירת העובדה
          </Button>
        </>
      }
      headingId={headingId}
      onClose={onClose}
      open={open}
      title="עריכת העובדה הממתינה"
    >
      <p className="text-support leading-6 text-cv-text-muted">
        העובדה נשארת ממתינה גם אחרי העריכה, ונחשבת רק אחרי שתאושר.
      </p>
      <form className="cv-fields-compact mt-4 flex flex-col gap-3" id={formId} onSubmit={form.handleSubmit(submit)}>
        <FactCoreFields {...fields} />
        <FactHebrewRenderingField register={form.register} />
        <FactTagsField {...fields} />
        {edit.error === null ? null : (
          <ErrorCallout error={edit.error} fallbackDetail="העובדה לא השתנתה. אפשר לנסות שוב." title="העובדה לא נשמרה" />
        )}
      </form>
    </Dialog>
  );
};
