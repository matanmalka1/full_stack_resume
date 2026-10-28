import { LayoutTemplate } from "lucide-react";
import { useId, useState } from "react";

import { documentTemplatePreviewSrc } from "@/api/documents";
import { type TemplateName, templateLabel } from "@/api/templates";
import { useSettings } from "@/features/settings";
import { TemplateGallery } from "@/features/templates";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Dialog } from "@/ui/Dialog";
import { ErrorCallout } from "@/ui/ErrorCallout";
import type { EditableDocument } from "../model/drafts.types";

interface DraftTemplateControlProps {
  disabled: boolean;
  draft: EditableDocument;
  /* Settles the editor, chooses the template, and reads the document back. The page owns
     it because the editor's save token is the page's: the template moves the hash. */
  onApply: (template: TemplateName | null) => Promise<void>;
  /* The document is approved or Ready: a new template returns it to draft. */
  stamped: boolean;
}

/* Which template the CV renders with, and the way to change it. The dialog shows the
   user's own saved CV in every template - the same server composition as the preview,
   nothing stored - so the comparison is of their document, not of a sample. Choosing
   in the dialog only selects; nothing changes until "apply". */
export const DraftTemplateControl = ({ disabled, draft, onApply, stamped }: DraftTemplateControlProps) => {
  const headingId = useId();
  const { settings } = useSettings();
  const options = settings?.available_templates ?? [];
  const current = draft.template ?? null;
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<TemplateName | null>(current);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const close = () => {
    if (pending) return;
    setOpen(false);
    setError(null);
  };
  const apply = async () => {
    setPending(true);
    setError(null);
    try {
      await onApply(selected);
      setOpen(false);
    } catch (failure) {
      setError(failure);
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-surface border border-cv-border bg-cv-surface px-3 py-2">
      <span className="flex min-w-0 items-center gap-2 text-support text-cv-text-muted">
        <LayoutTemplate aria-hidden="true" className="size-icon-md shrink-0" />
        תבנית: <span className="font-semibold text-cv-text">{templateLabel(options, current)}</span>
      </span>
      <Button
        disabled={disabled || settings === undefined}
        onClick={() => {
          setSelected(current);
          setOpen(true);
        }}
        size="compact"
        variant="secondary"
      >
        החלפת תבנית
      </Button>

      <Dialog
        description="קורות החיים השמורים שלך בכל אחת מהתבניות. התוכן לא משתנה, רק העיצוב."
        dismissible={!pending}
        /* The commands are the footer's own children, so the sheet's phone layout - two
           equal halves - reaches them; a wrapper of its own kept them content-wide. */
        footer={
          <>
            <Button disabled={pending} onClick={close} variant="secondary">
              ביטול
            </Button>
            <Button
              disabled={selected === current}
              onClick={() => void apply()}
              pending={pending}
              pendingLabel="מחליף…"
            >
              החלת התבנית
            </Button>
          </>
        }
        headingId={headingId}
        onClose={close}
        open={open}
        size="wide"
        title="בחירת תבנית"
      >
        <div className="flex flex-col gap-4">
          {stamped && selected !== current ? (
            <Callout title="המסמך יחזור לטיוטה" tone="warning">
              <p>הגרסה אושרה כבר בתבנית הנוכחית. אחרי ההחלפה יש לאשר וליצור את ה־PDF מחדש.</p>
            </Callout>
          ) : null}
          <TemplateGallery
            disabled={pending}
            name={`${headingId}-template`}
            onChange={setSelected}
            options={options}
            previewSrc={(template) => documentTemplatePreviewSrc(draft.application_id, draft.document_hash, template)}
            value={selected}
          />
          {error === null ? null : (
            <ErrorCallout
              error={error}
              fallbackDetail="התבנית לא הוחלפה. אפשר לנסות שוב."
              title="לא ניתן להחליף תבנית"
            />
          )}
        </div>
      </Dialog>
    </div>
  );
};
