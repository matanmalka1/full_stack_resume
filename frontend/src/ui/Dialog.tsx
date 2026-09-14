import { type ReactNode, useEffect, useRef } from "react";

import { surfaceClasses } from "./surface";
import { cx } from "./cx";
import { wrapDialogFocus } from "./dialogFocus";

/* Native <dialog> backdrop clicks are valid interaction; the lint rule classifies the
   element as non-interactive despite its built-in keyboard and cancel behavior. */
/* oxlint-disable jsx-a11y/no-noninteractive-element-interactions */
import { IconButton } from "./IconButton";

type DialogField = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

/* What the user has typed into this dialog, read from the dialog's own controls rather
   than from a per-dialog flag, so a form dialog added later is covered without being
   registered anywhere. The comparison is against a snapshot taken when the dialog opened,
   not against each element's `defaultValue`: a form library writes its defaults into the
   element, and `defaultValue` would report those writes as edits. */
const fieldState = (dialog: HTMLDialogElement): string =>
  Array.from(dialog.querySelectorAll<DialogField>("input, textarea, select"))
    .map((field, index) =>
      field instanceof HTMLInputElement && (field.type === "checkbox" || field.type === "radio")
        ? `${index}:${String(field.checked)}`
        : `${index}:${field.value}`,
    )
    .join("\u0000");

interface DialogProps {
  children: ReactNode;
  /* A.5: Escape cancels only when cancelling cannot approve, discard, or overwrite
     content. A conflict or approval dialog passes false and offers explicit choices. */
  dismissible?: boolean;
  footer?: ReactNode;
  headingId: string;
  onClose: () => void;
  open: boolean;
  size?: "default" | "wide";
  title: ReactNode;
}

/* Native <dialog> owns the inert background and focus restoration to the invoker.
   Tab wraps explicitly at the boundaries. Focus moves to the heading on open. */
export const Dialog = ({
  children,
  dismissible = true,
  footer,
  headingId,
  onClose,
  open,
  size = "default",
  title,
}: DialogProps) => {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const openedWith = useRef("");
  const heightClass = size === "wide" ? "max-h-[85dvh]" : "max-h-[calc(100dvh-2rem)]";

  useEffect(() => {
    const dialog = dialogRef.current;

    if (dialog === null) {
      return;
    }

    if (open && !dialog.open) {
      dialog.showModal();
      openedWith.current = fieldState(dialog);
      headingRef.current?.focus();
      return;
    }

    if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  return (
    <dialog
      aria-labelledby={headingId}
      className={surfaceClasses(
        `${heightClass} m-auto w-full ${
          size === "wide" ? "max-w-3xl" : "max-w-xl"
        } overflow-hidden bg-cv-surface p-0 text-cv-text shadow-overlay backdrop:transition-opacity`,
      )}
      onCancel={(event) => {
        if (!dismissible) {
          event.preventDefault();
        }
      }}
      onClick={(event) => {
        /* The backdrop is the one close a user reaches by accident, so it is the one that
           refuses to discard work. Escape and the dialog's own cancel controls are
           deliberate and still close; a click beside a dialog holding edits does nothing
           rather than silently throwing them away. */
        if (!dismissible || event.target !== event.currentTarget) {
          return;
        }
        if (fieldState(event.currentTarget) !== openedWith.current) {
          return;
        }
        onClose();
      }}
      onKeyDown={wrapDialogFocus}
      onClose={(event) => {
        /* A child dialog can close while this dialog remains open. React delegates the
           close event, so without stopping it here the child's event reaches an owning
           dialog and dismisses that one as well. */
        event.stopPropagation();
        onClose();
      }}
      ref={dialogRef}
    >
      <div className={cx("flex flex-col", heightClass)} dir="rtl">
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-cv-border px-6 py-5">
          <h2
            className="text-heading-md font-semibold tracking-tight text-cv-text"
            id={headingId}
            ref={headingRef}
            tabIndex={-1}
          >
            {title}
          </h2>
          {dismissible ? (
            <IconButton
              aria-label="סגירה"
              className="-me-2 -mt-1 text-cv-text-muted hover:text-cv-text"
              onClick={onClose}
            >
              <svg aria-hidden="true" className="size-icon-md" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" strokeWidth="var(--stroke-icon)" />
              </svg>
            </IconButton>
          ) : null}
        </div>
        <div className="min-h-0 overflow-y-auto px-6 py-5 text-body leading-7">{children}</div>
        {footer === undefined ? null : (
          <div className="flex shrink-0 flex-wrap justify-end gap-3 border-t border-cv-border px-6 py-4">{footer}</div>
        )}
      </div>
    </dialog>
  );
};
