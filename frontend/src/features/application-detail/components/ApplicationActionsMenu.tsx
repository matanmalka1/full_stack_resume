import {
  Archive,
  CircleCheck,
  Ellipsis,
  EllipsisVertical,
  FilePenLine,
  History,
  Info,
  type LucideIcon,
  Trash2,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cx } from "@/ui/cx";

interface ApplicationActionHandlers {
  onClose: () => void;
  onDelete: () => void;
  onDetails: () => void;
  /* Absent once the posting is locked by a Submission: the menu offers only what can be
     done. */
  onEditPosting?: () => void;
  onHistory: () => void;
  onUpdate: () => void;
}

interface ApplicationActionsMenuProps extends ApplicationActionHandlers {
  closed: boolean;
  company: string;
  /* Which trigger this is: the phone header's bare ⋮, or the outlined ⋯ beside the wide
     header's commands. Each is drawn only at its own width. */
  placement: "phone" | "desktop";
}

const itemClasses =
  "flex min-h-11 w-full items-center gap-3 rounded-item px-3 text-start text-label text-cv-text transition-colors hover:bg-cv-surface-muted focus-visible:bg-cv-surface-muted max-lg:min-h-13.5 max-lg:px-1 max-lg:text-body";

const MenuItem = ({
  icon: Icon,
  label,
  onSelect,
  strong = false,
}: {
  icon: LucideIcon;
  label: string;
  onSelect: () => void;
  strong?: boolean;
}) => (
  <button className={cx(itemClasses, strong && "font-bold")} onClick={onSelect} role="menuitem" type="button">
    <Icon aria-hidden="true" className="size-icon-lg shrink-0" />
    {label}
  </button>
);

/* The record's own commands, behind one trigger: update its status, read its details or
   its history, edit the posting it was saved with, close it, delete it. A wide screen opens them as a menu under the trigger;
   on a phone the same menu is an action sheet over the dimmed screen, under a handle and
   the company's name. It stays one menu either way - same items, same keys, same focus -
   so only its placement changes.

   Ending the record is set apart under a rule, and delete is written bold rather than
   coloured: the confirmation it opens is where its weight is stated. */
export const ApplicationActionsMenu = ({
  closed,
  company,
  onClose,
  onDelete,
  onDetails,
  onEditPosting,
  onHistory,
  onUpdate,
  placement,
}: ApplicationActionsMenuProps) => {
  const [open, setOpen] = useState(false);
  const menuId = `application-actions-${placement}`;
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const select = (action: () => void) => () => {
    setOpen(false);
    action();
  };

  useEffect(() => {
    if (!open) return;

    containerRef.current?.querySelector<HTMLElement>("[role=menuitem]")?.focus();
    const closeFromOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !containerRef.current?.contains(event.target)) setOpen(false);
    };
    const closeFromKeyboard = (event: globalThis.KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener("pointerdown", closeFromOutside);
    document.addEventListener("keydown", closeFromKeyboard);
    return () => {
      document.removeEventListener("pointerdown", closeFromOutside);
      document.removeEventListener("keydown", closeFromKeyboard);
    };
  }, [open]);

  const TriggerIcon = placement === "phone" ? EllipsisVertical : Ellipsis;

  return (
    <div
      className={cx(
        "relative shrink-0",
        placement === "phone" ? "lg:hidden" : "max-lg:hidden",
        open && "z-(--cv-z-overlay)",
      )}
      ref={containerRef}
    >
      <button
        aria-controls={menuId}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="פעולות נוספות"
        className={cx(
          "flex size-11 items-center justify-center rounded-control text-cv-text transition-colors hover:bg-cv-surface-muted",
          placement === "desktop" && "border bg-cv-surface",
          placement === "desktop" && (open ? "border-cv-text" : "border-cv-border"),
        )}
        onClick={() => setOpen((current) => !current)}
        ref={triggerRef}
        type="button"
      >
        <TriggerIcon aria-hidden="true" className="size-icon-lg" />
      </button>
      {open ? (
        // Escape and the menu's own items are the keyboard's ways out; this is the pointer's.
        // oxlint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
        <div aria-hidden="true" className="fixed inset-0 bg-cv-scrim lg:hidden" onClick={() => setOpen(false)} />
      ) : null}
      {open ? (
        <div
          aria-label={`ניהול מועמדות: ${company}`}
          className="absolute end-0 top-full mt-1.5 w-70 rounded-surface border border-cv-hairline bg-cv-surface-raised p-1.5 shadow-overlay max-lg:fixed max-lg:inset-x-0 max-lg:top-auto max-lg:bottom-0 max-lg:mt-0 max-lg:w-auto max-lg:rounded-t-sheet max-lg:rounded-b-none max-lg:border-0 max-lg:px-5 max-lg:pt-0 max-lg:pb-[calc(env(safe-area-inset-bottom)+1rem)] max-lg:shadow-sheet"
          id={menuId}
          onKeyDown={(event) => {
            if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
            event.preventDefault();
            const items = [...event.currentTarget.querySelectorAll<HTMLElement>("[role=menuitem]")];
            const currentIndex = items.indexOf(document.activeElement as HTMLElement);
            const nextIndex =
              event.key === "Home"
                ? 0
                : event.key === "End"
                  ? items.length - 1
                  : (currentIndex + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
            items[nextIndex]?.focus();
          }}
          role="menu"
          tabIndex={-1}
        >
          <div aria-hidden="true" className="lg:hidden">
            <div className="mx-auto mt-2 h-1.25 w-10 rounded-pill bg-cv-border-soft" />
            <p className="pt-4 pb-1 text-support font-bold text-cv-text-muted" dir="auto">
              ניהול מועמדות: {company}
            </p>
          </div>
          <MenuItem icon={CircleCheck} label="עדכון סטטוס ומשימות" onSelect={select(onUpdate)} />
          <MenuItem icon={Info} label="פרטי משרה" onSelect={select(onDetails)} />
          {onEditPosting === undefined ? null : (
            <MenuItem icon={FilePenLine} label="עריכת נוסח המשרה" onSelect={select(onEditPosting)} />
          )}
          <MenuItem icon={History} label="היסטוריית המועמדות" onSelect={select(onHistory)} />
          <hr className="mx-2 my-1.5 border-0 border-t border-cv-hairline max-lg:mx-0" />
          {closed ? null : <MenuItem icon={Archive} label="סגירת המועמדות" onSelect={select(onClose)} />}
          <MenuItem icon={Trash2} label="מחיקת המועמדות" onSelect={select(onDelete)} strong />
        </div>
      ) : null}
    </div>
  );
};
