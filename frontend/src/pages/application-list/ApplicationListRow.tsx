import { Archive, ArrowLeft, Clock, FileCheck2 } from "lucide-react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "../../api/contracts";
import { isTerminalOperation } from "../../api/operations";
import { Button } from "../../ui/Button";
import { StatusBadge } from "../../ui/StatusBadge";
import { actionDestination } from "../actionDestinations";
import {
  actionLabel,
  preparationStateIcons,
  preparationStateLabels,
  preparationStateTones,
  recruitmentStatusIcon,
  recruitmentStatusLabel,
  recruitmentStatusTone,
} from "../applicationLabels";
import { operationTypeLabels, statusLabels } from "../operationLabels";
import {
  applicationAttention,
  formatApplicationDate,
  isApplicationClosed,
  isNextActionOverdue,
} from "./applicationListPresentation";

const CompanyMark = ({ company }: { company: string }) => (
  <span
    aria-hidden="true"
    className="flex size-9 shrink-0 items-center justify-center rounded-control bg-cv-accent-soft text-support font-bold text-cv-accent"
  >
    {[...company][0] ?? "?"}
  </span>
);

const rowActionClasses =
  "inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-pill bg-cv-accent-soft px-3.5 text-support font-semibold text-cv-accent transition-colors duration-200 hover:bg-cv-accent hover:text-cv-on-accent";

const RecruitmentStatusCell = ({ item }: { item: ApplicationListItem }) => {
  const closed = isApplicationClosed(item);

  return (
    <td className="px-4 py-3.5">
      <div className="flex flex-col items-start gap-1">
        <StatusBadge
          className="whitespace-nowrap"
          icon={recruitmentStatusIcon(item.recruitment_status)}
          tone={recruitmentStatusTone(item.recruitment_status)}
        >
          {recruitmentStatusLabel(item.recruitment_status)}
        </StatusBadge>
        {closed ? <span className="text-support text-cv-text-muted">התהליך נסגר</span> : null}
      </div>
    </td>
  );
};

const NextActionCell = ({ item }: { item: ApplicationListItem }) => {
  const overdue = isNextActionOverdue(item.next_action_date);

  return (
    <td className="px-4 py-3.5">
      {item.next_action == null ? (
        <span className="text-support text-cv-text-muted">טרם נקבעה</span>
      ) : (
        <div className="flex flex-col items-start gap-1">
          <span className="text-support text-cv-text" dir="auto">
            {item.next_action}
          </span>
          {item.next_action_date == null ? null : (
            <span className="flex items-center gap-1.5 text-support text-cv-text-muted">
              {overdue ? (
                <StatusBadge className="gap-1 px-2 py-0.5" tone="warning">
                  באיחור
                </StatusBadge>
              ) : null}
              <span className="inline-flex items-center gap-1.5">
                <Clock aria-hidden="true" className="size-3.5 shrink-0" />
                {formatApplicationDate(item.next_action_date)}
              </span>
            </span>
          )}
        </div>
      )}
    </td>
  );
};

const RecommendedActionCell = ({ item }: { item: ApplicationListItem }) => {
  const href = `/applications/${encodeURIComponent(item.id)}`;
  const running =
    item.active_operation != null && !isTerminalOperation(item.active_operation)
      ? item.active_operation
      : null;

  return (
    <td className="whitespace-nowrap px-4 py-3.5">
      <div className="flex items-center">
        {running !== null ? (
          <StatusBadge tone="progress">
            {operationTypeLabels[running.operation_type]} · {statusLabels[running.status]}
          </StatusBadge>
        ) : item.latest_ready_revision_id != null ? (
          <Link
            className={rowActionClasses}
            to={`/approved-revisions/${encodeURIComponent(item.latest_ready_revision_id)}/ready`}
          >
            <FileCheck2 aria-hidden="true" className="size-4" />
            הגרסה המוכנה
          </Link>
        ) : item.recommended_action == null ? (
          <span className="text-support text-cv-text-muted">—</span>
        ) : (
          <Link
            className={rowActionClasses}
            to={actionDestination(item.recommended_action, item.id) ?? href}
          >
            <ArrowLeft aria-hidden="true" className="size-4" />
            {actionLabel(item.recommended_action)}
          </Link>
        )}
      </div>
    </td>
  );
};

interface ApplicationListRowProps {
  ambiguous: boolean;
  item: ApplicationListItem;
  onRequestClose: (item: ApplicationListItem) => void;
}

export const ApplicationListRow = ({
  ambiguous,
  item,
  onRequestClose,
}: ApplicationListRowProps) => {
  const href = `/applications/${encodeURIComponent(item.id)}`;
  const attention = applicationAttention(item);
  const closed = isApplicationClosed(item);

  return (
    <tr className="border-b border-cv-border last:border-b-0 hover:bg-cv-surface-muted">
      <td className="px-4 py-3.5">
        <div className="flex min-w-0 items-center gap-2">
          <CompanyMark company={item.company} />
          <div className="min-w-0 flex-1 text-left">
            <Link
              className="block truncate text-support font-bold text-cv-text hover:underline"
              dir="auto"
              to={href}
            >
              {item.company}
            </Link>
            <p className="truncate text-support text-cv-text-muted" dir="auto">
              {item.target_role}
            </p>
          </div>
        </div>
      </td>
      <td className="whitespace-nowrap px-4 py-3.5 text-support">
        <span className={ambiguous ? "font-medium text-cv-text" : "text-cv-text-muted"}>
          {formatApplicationDate(item.created_at)}
        </span>
      </td>
      <td className="px-4 py-3.5">
        <StatusBadge
          className="whitespace-nowrap"
          icon={preparationStateIcons[item.preparation_state]}
          tone={preparationStateTones[item.preparation_state]}
        >
          {preparationStateLabels[item.preparation_state]}
        </StatusBadge>
      </td>
      <RecruitmentStatusCell item={item} />
      <td className="whitespace-nowrap px-4 py-3.5 text-support text-cv-text-muted">
        <span className="inline-flex items-center gap-1.5">
          <Clock aria-hidden="true" className="size-3.5 shrink-0" />
          {formatApplicationDate(item.updated_at)}
        </span>
      </td>
      <NextActionCell item={item} />
      <td className="px-4 py-3.5 text-center">
        {attention === null ? (
          <span className="text-support text-cv-text-muted">—</span>
        ) : (
          <StatusBadge className="whitespace-nowrap" tone={attention.tone}>
            {attention.label}
          </StatusBadge>
        )}
      </td>
      <RecommendedActionCell item={item} />
      <td className="px-4 py-3.5">
        {closed ? null : (
          <Button
            aria-label={`סגירת המועמדות ${item.company}`}
            className="px-2"
            onClick={() => onRequestClose(item)}
            variant="ghost"
          >
            <Archive aria-hidden="true" className="size-4" />
          </Button>
        )}
      </td>
    </tr>
  );
};
