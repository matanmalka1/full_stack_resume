import { type ReactNode, type RefObject, useEffect, useRef } from "react";

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
  /* One line under the title, in the header: what the dialog is about, not its content.
     It becomes the dialog's accessible description. */
  description?: ReactNode;
  /* A.5: Escape cancels only when cancelling cannot approve, discard, or overwrite
     content. A conflict or approval dialog passes false and offers explicit choices. */
  dismissible?: boolean;
  footer?: ReactNode;
  /* How the footer's commands sit on a phone. "row" (the default) puts them side by side
     in equal halves; "stack" puts each on its own full-width line, for commands whose
     labels are sentences - the draft conflict's two ways out. The footer stays a flex
     container either way, so a caller may still reorder a command with `order-*`. */
  footerLayout?: "row" | "stack";
  headingId: string;
  /* A mark over the title naming what the dialog is about - archive, delete, rebuild.
     Drawn below the large breakpoint only, where a centred confirmation leads with it;
     the desktop dialog's header has no place for it. Decorative: the title says it. */
  icon?: ReactNode;
  onClose: () => void;
  open: boolean;
  /* How the dialog stands on a phone - below the large breakpoint; from it every dialog is
     the same centred surface. A "sheet" (the default) rises from the bottom edge, full
     width, under a grab handle: it holds a form or a record, and a thumb reaches its
     commands there. An "alert" stays a centred card - a two-answer question that should
     interrupt, as `ConfirmDialog` asks it. */
  presentation?: "sheet" | "alert";
  /* Where focus goes once the dialog closes, for a dialog that is not always opened by
     the control that reopens it. Native restoration returns focus to whatever held it at
     `showModal()`, which for a dialog the screen opened by itself is an unrelated control,
     or one that has since left the page. Absent, native restoration stands. */
  restoreFocusTo?: RefObject<HTMLElement | null>;
  size?: "default" | "wide";
  title: ReactNode;
}

/* Native <dialog> owns the inert background and focus restoration to the invoker.
   Tab wraps explicitly at the boundaries. Focus moves to the heading on open. */
export const Dialog = ({
  children,
  description,
  dismissible = true,
  footer,
  footerLayout = "row",
  headingId,
  icon,
  onClose,
  open,
  presentation = "sheet",
  restoreFocusTo,
  size = "default",
  title,
}: DialogProps) => {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const openedWith = useRef("");
  const heightClass = size === "wide" ? "max-h-[85dvh]" : "max-h-[calc(100dvh-2rem)]";
  const sheet = presentation === "sheet";

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
      aria-describedby={description === undefined ? undefined : `${headingId}-description`}
      aria-labelledby={headingId}
      className={surfaceClasses(
        cx(
          `${heightClass} m-auto w-full ${
            size === "wide" ? "max-w-3xl" : "max-w-xl"
          } overflow-hidden bg-cv-surface p-0 text-cv-text shadow-overlay backdrop:transition-opacity`,
          /* The sheet drops to the bottom edge - a modal dialog is fixed to the viewport,
             so a zero bottom margin under an auto top one is the whole anchoring - and
             spans the width with only its top corners rounded. Below `sm` the UA's own
             max-width would leave a gutter beside it, so the width cap goes too. */
          sheet
            ? "cv-sheet max-lg:mb-0 max-lg:rounded-t-sheet max-lg:rounded-b-none max-lg:border-b-0 max-sm:max-w-none"
            : "max-lg:w-[calc(100%-2rem)] max-lg:rounded-sheet",
        ),
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
        restoreFocusTo?.current?.focus();
      }}
      ref={dialogRef}
    >
      {/* The bottom padding keeps a sheet's last control above the home indicator. It is
          zero wherever the device has no such inset, and a centred dialog never meets it. */}
      <div className={cx("flex flex-col", heightClass, sheet && "max-lg:pb-[env(safe-area-inset-bottom)]")} dir="rtl">
        {/* Drawn, not a control: a sheet is closed by its X, Escape or the backdrop. The
            handle only says what kind of surface this is. */}
        {sheet ? (
          <div aria-hidden="true" className="mx-auto mt-2 h-1.5 w-10 shrink-0 rounded-pill bg-cv-border lg:hidden" />
        ) : null}
        <div
          className={cx(
            "flex shrink-0 items-start justify-between gap-4 border-b border-cv-border px-6 py-5",
            sheet
              ? "max-lg:border-b-0 max-lg:px-4 max-lg:pt-2.5 max-lg:pb-3"
              : "max-lg:border-b-0 max-lg:px-5 max-lg:pt-5 max-lg:pb-3",
          )}
        >
          <div className="min-w-0">
            {icon === undefined ? null : (
              <div aria-hidden="true" className="mb-3.5 lg:hidden">
                {icon}
              </div>
            )}
            <h2
              className="text-heading-md font-semibold tracking-tight text-cv-text max-lg:font-extrabold"
              id={headingId}
              ref={headingRef}
              tabIndex={-1}
            >
              {title}
            </h2>
            {description === undefined ? null : (
              <p className="mt-1 text-support text-cv-text-muted" id={`${headingId}-description`}>
                {description}
              </p>
            )}
          </div>
          {/* A phone's confirmation is closed by its own two answers, as the design draws
              it; Escape still cancels it. */}
          {dismissible ? (
            <IconButton
              aria-label="סגירה"
              className={cx("-me-2 -mt-1 text-cv-text-muted hover:text-cv-text", !sheet && "max-lg:hidden")}
              onClick={onClose}
            >
              <svg aria-hidden="true" className="size-icon-md" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" strokeWidth="var(--stroke-icon)" />
              </svg>
            </IconButton>
          ) : null}
        </div>
        <div
          className={cx(
            "min-h-0 overflow-y-auto px-6 py-5 text-body leading-7",
            sheet ? "max-lg:px-4 max-lg:pt-1 max-lg:pb-4" : "max-lg:px-5 max-lg:pt-0 max-lg:pb-2",
          )}
        >
          {children}
        </div>
        {/* On a phone the commands share the row's full width, each one a thumb-sized
            target, as a phone's own sheets and alerts draw them. Cancel stays first, so in
            RTL it keeps the start edge and the command the closing one, as on desktop. */}
        {footer === undefined ? null : (
          <div
            className={cx(
              "flex shrink-0 flex-wrap justify-end gap-3 border-t border-cv-border px-6 py-4",
              "max-lg:gap-2 max-lg:text-body max-lg:*:min-h-12",
              footerLayout === "stack" ? "max-lg:flex-col max-lg:*:w-full" : "max-lg:*:flex-1",
              sheet ? "max-lg:px-4 max-lg:pt-3" : "max-lg:border-t-0 max-lg:px-5 max-lg:pt-3 max-lg:pb-5",
            )}
          >
            {footer}
          </div>
        )}
      </div>
    </dialog>
  );
};
