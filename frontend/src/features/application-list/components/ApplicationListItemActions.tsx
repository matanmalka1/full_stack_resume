import { Archive, EllipsisVertical, ExternalLink, Eye, SlidersHorizontal, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";
import { Tooltip } from "@/ui/Tooltip";
import { sourceHostname } from "@/features/applications";
import { preparationResumeDestination } from "@/features/preparation";

/* Terminal only means polling may stop. A failed or interrupted run remains the most
   important next-action fact until a newer run supersedes it; successful and deliberately
   cancelled work yield back to the projection's normal recommendation. */
export const reportedOperation = (item: ApplicationListItem) => {
  const latest = item.active_operation ?? item.latest_operation;

  return latest != null &&
    (!isTerminalOperation(latest) || latest.status === "failed" || latest.status === "interrupted")
    ? latest
    : null;
};

const menuItemBase =
  "flex min-h-9 w-full items-center gap-2 px-3.5 py-2 text-start text-support font-medium transition-colors";
const menuItemClasses = `${menuItemBase} text-cv-text hover:bg-cv-surface-muted`;

export const ApplicationRecordActions = ({
  item,
  onRequestClose,
  onRequestDelete,
  onRequestUpdate,
}: {
  item: ApplicationListItem;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestDelete: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}) => {
  const [open, setOpen] = useState(false);
  const href = preparationResumeDestination(item);
  const host = sourceHostname(item.source_url);
  const menuId = `application-actions-${item.id}`;
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

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

  return (
    <div className="relative z-(--cv-z-content-raised) shrink-0" ref={containerRef}>
      <Tooltip label="פעולות נוספות">
        <button
          aria-controls={menuId}
          aria-expanded={open}
          aria-haspopup="menu"
          aria-label={`פעולות נוספות עבור ${item.company}`}
          className="inline-flex size-9 items-center justify-center rounded-control text-cv-text-muted transition-colors hover:bg-cv-surface-muted hover:text-cv-text"
          onClick={() => setOpen((current) => !current)}
          ref={triggerRef}
          type="button"
        >
          <EllipsisVertical aria-hidden="true" className="size-icon-md" />
        </button>
      </Tooltip>
      {open ? (
        <div
          className="absolute end-0 top-full z-(--cv-z-sticky) mt-1.5 w-56 divide-y divide-cv-border rounded-surface border border-cv-border bg-cv-surface-raised py-1.5 text-start shadow-floating"
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
          {/* Two groups, as in demo_re: the ways into the record, then the two that end
              it. The ending pair keeps the blocker tone; nothing else here is coloured. */}
          <div className="py-1">
            <Link className={menuItemClasses} onClick={() => setOpen(false)} role="menuitem" to={href}>
              <Eye aria-hidden="true" className="size-icon-md shrink-0 text-cv-text-muted" />
              פתיחת המועמדות
            </Link>
            {host === null || item.source_url == null ? null : (
              <a
                className={menuItemClasses}
                href={item.source_url}
                onClick={() => setOpen(false)}
                rel="noreferrer"
                role="menuitem"
                target="_blank"
              >
                <ExternalLink aria-hidden="true" className="size-icon-md shrink-0 text-cv-text-muted" />
                <span className="flex min-w-0 flex-col">
                  מודעת המשרה המקורית
                  <span className="truncate text-cv-text-muted" dir="ltr">
                    {host}
                  </span>
                </span>
              </a>
            )}
            <button
              className={menuItemClasses}
              onClick={() => {
                setOpen(false);
                onRequestUpdate(item);
              }}
              role="menuitem"
              type="button"
            >
              <SlidersHorizontal aria-hidden="true" className="size-icon-md shrink-0 text-cv-text-muted" />
              עדכון סטטוס ומשימות
            </button>
          </div>
          <div className="py-1">
            {item.is_closed ? null : (
              <button
                aria-label={`סגירת המועמדות ${item.company}`}
                className={menuItemClasses}
                onClick={() => {
                  setOpen(false);
                  onRequestClose(item);
                }}
                role="menuitem"
                type="button"
              >
                <Archive aria-hidden="true" className="size-icon-md shrink-0 text-cv-text-muted" />
                סגירת מועמדות
              </button>
            )}
            <button
              aria-label={`מחיקת המועמדות ${item.company}`}
              className={`${menuItemBase} text-cv-blocker hover:bg-cv-blocker-soft`}
              onClick={() => {
                setOpen(false);
                onRequestDelete(item);
              }}
              role="menuitem"
              type="button"
            >
              <Trash2 aria-hidden="true" className="size-icon-md shrink-0" />
              מחיקת מועמדות לצמיתות
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
};
