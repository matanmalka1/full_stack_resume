import { Archive, ArrowLeft, FileCheck2, SlidersHorizontal } from "lucide-react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "../../api/contracts";
import { isTerminalOperation } from "../../api/operations";
import { appRoutes } from "../../app/appRoutes";
import { Button } from "../../ui/Button";
import { StatusBadge } from "../../ui/StatusBadge";
import { actionDestination } from "../application/actionDestinations";
import { actionLabel } from "../application/applicationLabels";
import { operationTypeLabels, statusLabels, statusTones } from "../operationLabels";
import type { ApplicationListViewVariant } from "./ApplicationListParts";

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
  /* A ready revision does not suppress newer recommended work: both can be valid when
     the posting or policy changed after that revision was approved. */
  const readyRevisionLink =
    item.latest_ready_revision_id == null ? null : (
      <Link className={revisionLinkClasses[variant]} to={appRoutes.revision(item.latest_ready_revision_id)}>
        <FileCheck2 aria-hidden="true" className={variant === "row" ? "size-3.5 shrink-0" : "size-4 shrink-0"} />
        הגרסה המוכנה
      </Link>
    );

  return (
    <div className={variant === "row" ? "flex flex-col items-start gap-1" : "flex flex-col items-end gap-1.5"}>
      {operation !== null ? (
        <StatusBadge
          className={variant === "row" ? "gap-1.5 px-2.5 text-start" : "px-2.5"}
          tone={statusTones[operation.status]}
        >
          {operationTypeLabels[operation.operation_type]} · {statusLabels[operation.status]}
        </StatusBadge>
      ) : item.recommended_action != null ? (
        <Link
          className={actionClasses[variant]}
          to={actionDestination(item.recommended_action, item.id) ?? appRoutes.application(item.id)}
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
}) => (
  <div className="flex shrink-0 items-center gap-0.5">
    <button
      aria-label={`עדכון סטטוס ומשימות עבור ${item.company}`}
      className="inline-flex min-h-9 items-center rounded-control px-2 text-cv-text-muted transition-colors hover:bg-cv-surface-muted hover:text-cv-text"
      onClick={() => onRequestUpdate(item)}
      title="עדכון סטטוס ומשימות"
      type="button"
    >
      <SlidersHorizontal aria-hidden="true" className="size-4" />
    </button>
    {item.is_closed ? null : (
      <Button
        aria-label={`סגירת המועמדות ${item.company}`}
        className="min-h-9 px-2 text-cv-text-muted hover:text-cv-blocker"
        onClick={() => onRequestClose(item)}
        title="סגירת מועמדות"
        variant="ghost"
      >
        <Archive aria-hidden="true" className="size-4" />
      </Button>
    )}
  </div>
);
