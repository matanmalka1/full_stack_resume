import { type ReactNode, useId, useState } from "react";

import type { PreviewTemplate, TemplateName, TemplateOption } from "@/api/templates";
import { Button } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { TemplateGallery } from "./TemplateGallery";

interface TemplatePickerDialogProps {
  applyLabel: string;
  /* Shown above the gallery while the selection differs from the current template. */
  changeWarning?: ReactNode;
  current: TemplateName | null;
  description: string;
  /* Takes the selection. A rejection keeps the dialog open with the error. */
  onApply: (template: TemplateName | null) => Promise<void> | void;
  onClose: () => void;
  open: boolean;
  options: readonly TemplateOption[];
  previewSrc: (template: PreviewTemplate) => string;
  /* Shown above the gallery throughout: a control over what the thumbnails show. */
  toolbar?: ReactNode;
}

/* Choosing a template by sight: the gallery in a dialog. Choosing in it only selects;
   nothing reaches the caller until "apply". The editor applies to the user's own CV, and
   Settings take the default for new ones. */
export const TemplatePickerDialog = ({
  applyLabel,
  changeWarning,
  current,
  description,
  onApply,
  onClose,
  open,
  options,
  previewSrc,
  toolbar,
}: TemplatePickerDialogProps) => {
  const headingId = useId();
  const [selected, setSelected] = useState<TemplateName | null>(current);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  /* Each opening starts from the current template, not from the last one looked at. */
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setSelected(current);
      setError(null);
    }
  }

  const close = () => {
    if (!pending) onClose();
  };
  const apply = async () => {
    setPending(true);
    setError(null);
    try {
      await onApply(selected);
      onClose();
    } catch (failure) {
      setError(failure);
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog
      description={description}
      dismissible={!pending}
      /* The commands are the footer's own children, so the sheet's phone layout - two
         equal halves - reaches them; a wrapper of its own kept them content-wide. */
      footer={
        <>
          <Button disabled={pending} onClick={close} variant="secondary">
            ביטול
          </Button>
          <Button disabled={selected === current} onClick={() => void apply()} pending={pending} pendingLabel="מחליף…">
            {applyLabel}
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
        {toolbar}
        {selected === current ? null : changeWarning}
        <TemplateGallery
          disabled={pending}
          name={`${headingId}-template`}
          onChange={setSelected}
          options={options}
          previewSrc={previewSrc}
          value={selected}
        />
        {error === null ? null : (
          <ErrorCallout error={error} fallbackDetail="התבנית לא הוחלפה. אפשר לנסות שוב." title="לא ניתן להחליף תבנית" />
        )}
      </div>
    </Dialog>
  );
};
