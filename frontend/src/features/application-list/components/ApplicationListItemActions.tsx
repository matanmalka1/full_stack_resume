import { Archive, ArrowLeft, CircleAlert, Ellipsis, FileCheck2, SlidersHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";
import { routePaths } from "@/app/routePaths";
import { Button } from "@/ui/Button";
import { StatusBadge } from "@/ui/StatusBadge";
import { Tooltip } from "@/ui/Tooltip";
import { actionDestination } from "@/features/preparation";
import { actionLabel } from "@/features/preparation";
import { operationTypeLabels, statusLabels, statusTones } from "@/features/operations";
import type { ApplicationListViewVariant } from "../model/applicationList.types";

type ActionVariant = Exclude<ApplicationListViewVariant, "pipeline">;

const actionClasses: Record<ActionVariant, string> = {
  card: "inline-flex min-h-9 items-center gap-1.5 rounded-pill bg-cv-accent-soft px-3 text-support font-semibold text-cv-accent hover:bg-cv-accent hover:text-cv-on-accent",
  row: "inline-flex min-h-9 items-center justify-center gap-2 rounded-pill bg-cv-accent-soft px-3 py-1 text-start text-support font-semibold text-cv-accent transition-colors duration-200 hover:bg-cv-accent hover:text-cv-on-accent",
};

const revisionLinkClasses: Record<ActionVariant, string> = {
  card: "inline-flex items-center gap-1.5 text-support font-semibold text-cv-accent hover:underline",
  row: "inline-flex items-center gap-1.5 rounded-pill text-support font-semibold text-cv-accent hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cv-focus",
};

/* Terminal only means polling may stop. A failed or interrupted run remains the most
   important next-action fact until a newer run supersedes it; successful and deliberately
   cancelled work yield back to the projection's normal recommendation. */
const reportedOperation = (item: ApplicationListItem) => {
  const latest = item.active_operation ?? item.latest_operation;

  return latest != null &&
    (!isTerminalOperation(latest) || latest.status === "failed" || latest.status === "interrupted")
    ? latest
    : null;
};

export const ApplicationRecommendedAction = ({
  item,
  variant,
}: {
  item: ApplicationListItem;
  variant: ActionVariant;
}) => {
  const operation = reportedOperation(item);
  const operationFailed = operation?.status === "failed" || operation?.status === "interrupted";
  /* A ready revision does not suppress newer recommended work: both can be valid when
     the posting or policy changed after that revision was approved. */
  const readyRevisionLink =
    item.latest_ready_revision_id == null ? null : (
      <Link className={revisionLinkClasses[variant]} to={routePaths.revision(item.latest_ready_revision_id)}>
        <FileCheck2 aria-hidden="true" className={variant === "row" ? "size-3.5 shrink-0" : "size-4 shrink-0"} />
        הגרסה המוכנה
      </Link>
    );

  return (
    <div className={variant === "row" ? "flex flex-col items-start gap-1" : "flex flex-col items-end gap-1.5"}>
      {operationFailed && operation !== null ? (
        <span
          className="inline-flex max-w-full items-start gap-1.5 text-start text-support font-medium text-cv-blocker"
          title={`${operationTypeLabels[operation.operation_type]} · ${statusLabels[operation.status]}`}
        >
          <CircleAlert aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          <span className="line-clamp-2">
            {operationTypeLabels[operation.operation_type]} · {statusLabels[operation.status]}
          </span>
        </span>
      ) : operation !== null ? (
        <StatusBadge
          className={variant === "row" ? "gap-1.5 px-2.5 text-start" : "px-2.5"}
          tone={statusTones[operation.status]}
        >
          {operationTypeLabels[operation.operation_type]} · {statusLabels[operation.status]}
        </StatusBadge>
      ) : item.recommended_action != null ? (
        <Link
          className={actionClasses[variant]}
          to={actionDestination(item.recommended_action, item.id) ?? routePaths.application(item.id)}
        >
          <ArrowLeft aria-hidden="true" className="size-4" />
          {actionLabel(item.recommended_action)}
        </Link>
      ) : readyRevisionLink === null && variant === "row" ? (
        <span className="text-support text-cv-text-muted">—</span>
      ) : null}
      {operation === null ? readyRevisionLink : null}
    </div>
  );
};

export const ApplicationRecordActions = ({
  item,
  onRequestClose,
  onRequestUpdate,
}: {
  item: ApplicationListItem;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}) => {
  const [open, setOpen] = useState(false);
  const menuId = `application-actions-${item.id}`;
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    containerRef.current?.querySelector<HTMLButtonElement>("[role=menuitem]")?.focus();
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
    <div className="relative z-content-raised shrink-0" ref={containerRef}>
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
          <Ellipsis aria-hidden="true" className="size-4" />
        </button>
      </Tooltip>
      {open ? (
        <div
          className="absolute end-0 top-full z-sticky mt-1 min-w-52 rounded-control border border-cv-border bg-cv-surface-raised p-1 shadow-floating"
          id={menuId}
          onKeyDown={(event) => {
            if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
            event.preventDefault();
            const items = [...event.currentTarget.querySelectorAll<HTMLButtonElement>("[role=menuitem]")];
            const currentIndex = items.indexOf(document.activeElement as HTMLButtonElement);
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
          <button
            className="flex min-h-9 w-full items-center gap-2 rounded-control px-3 text-start text-support font-medium text-cv-text hover:bg-cv-surface-muted"
            onClick={() => {
              setOpen(false);
              onRequestUpdate(item);
            }}
            role="menuitem"
            type="button"
          >
            <SlidersHorizontal aria-hidden="true" className="size-4 text-cv-text-muted" />
            עדכון סטטוס ומשימות
          </button>
          {item.is_closed ? null : (
            <Button
              aria-label={`סגירת המועמדות ${item.company}`}
              className="min-h-9 w-full justify-start rounded-control px-3 text-cv-blocker hover:bg-cv-blocker-soft"
              onClick={() => {
                setOpen(false);
                onRequestClose(item);
              }}
              role="menuitem"
              variant="ghost"
            >
              <Archive aria-hidden="true" className="size-4" />
              סגירת מועמדות
            </Button>
          )}
        </div>
      ) : null}
    </div>
  );
};
