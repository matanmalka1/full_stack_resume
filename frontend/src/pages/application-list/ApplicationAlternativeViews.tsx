import { AlertTriangle, Archive, ArrowLeft, Clock, FileCheck2, SlidersHorizontal } from "lucide-react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "../../api/contracts";
import { isTerminalOperation } from "../../api/operations";
import { Button } from "../../ui/Button";
import { StatusBadge } from "../../ui/StatusBadge";
import { cx } from "../../ui/cx";
import { actionDestination } from "../application/actionDestinations";
import { fitLevelIcon, fitLevelLabel, fitLevelTone, trackLabel } from "../application/analysisLabels";
import {
  actionLabel,
  preparationStateIcons,
  preparationStateLabels,
  preparationStateTones,
  recruitmentStatusLabel,
} from "../application/applicationLabels";
import { operationTypeLabels, statusLabels, statusTones } from "../operationLabels";
import {
  applicationAttention,
  formatApplicationDate,
  isApplicationClosed,
  isNextActionOverdue,
  sourceHost,
} from "./applicationListPresentation";

interface AlternativeViewProps {
  items: readonly ApplicationListItem[];
  onRequestClose: (item: ApplicationListItem) => void;
}

const CompanyMark = ({ company }: { company: string }) => (
  <span
    aria-hidden="true"
    className="flex size-11 shrink-0 items-center justify-center rounded-control border border-cv-accent/20 bg-cv-accent-soft text-support font-extrabold text-cv-accent shadow-surface"
  >
    {[...company].slice(0, 2).join("").toLocaleUpperCase() || "?"}
  </span>
);

const Provenance = ({ item }: { item: ApplicationListItem }) => {
  const host = sourceHost(item.source_url);
  const origin = host ?? (item.source === "manual" ? null : item.source);

  if (item.track == null && origin == null) {
    return null;
  }

  return (
    <p className="truncate text-support text-cv-text-muted">
      {item.track == null ? null : trackLabel(item.track)}
      {item.track != null && origin != null ? " · " : null}
      {origin}
    </p>
  );
};

const ApplicationCard = ({
  item,
  onRequestClose,
}: {
  item: ApplicationListItem;
  onRequestClose: AlternativeViewProps["onRequestClose"];
}) => {
  const href = `/applications/${encodeURIComponent(item.id)}`;
  const attention = applicationAttention(item);
  const closed = isApplicationClosed(item);
  const nextActionOverdue = !closed && isNextActionOverdue(item.next_action_date);
  const latestOperation = item.active_operation ?? item.latest_operation;
  const reportedOperation =
    latestOperation != null &&
    (!isTerminalOperation(latestOperation) ||
      latestOperation.status === "failed" ||
      latestOperation.status === "interrupted")
      ? latestOperation
      : null;

  return (
    <article className="group flex h-full flex-col rounded-surface border border-cv-border bg-cv-surface-raised p-5 shadow-surface transition-all hover:border-cv-border-strong hover:shadow-floating">
      <div className="flex-1">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <CompanyMark company={item.company} />
            <div className="min-w-0 text-left">
              <Link
                className="block truncate font-extrabold text-cv-text transition-colors group-hover:text-cv-accent hover:underline"
                dir="auto"
                to={href}
              >
                {item.company}
              </Link>
              <p className="truncate text-support text-cv-text-muted" dir="auto" title={item.target_role}>
                {item.target_role}
              </p>
              <Provenance item={item} />
            </div>
          </div>
          {item.fit_level == null ? null : (
            <StatusBadge
              className="shrink-0 px-2 py-0.5"
              icon={fitLevelIcon(item.fit_level)}
              tone={fitLevelTone(item.fit_level)}
            >
              {fitLevelLabel(item.fit_level)}
            </StatusBadge>
          )}
        </div>

        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          <StatusBadge className="px-2.5 py-0.5" tone="neutral">
            {recruitmentStatusLabel(item.recruitment_status)}
          </StatusBadge>
          <StatusBadge
            className="px-2.5 py-0.5"
            icon={preparationStateIcons[item.preparation_state]}
            tone={preparationStateTones[item.preparation_state]}
          >
            {preparationStateLabels[item.preparation_state]}
          </StatusBadge>
        </div>

        {item.next_action == null ? null : (
          <div
            className={cx(
              "mb-3 rounded-control border px-3 py-2 text-support",
              nextActionOverdue
                ? "border-cv-blocker/30 bg-cv-blocker-soft text-cv-blocker"
                : "border-cv-border bg-cv-surface-muted text-cv-text",
            )}
          >
            <div className="mb-1 flex items-center justify-between gap-2 font-semibold">
              <span className="inline-flex items-center gap-1.5 text-cv-text-muted">
                <Clock aria-hidden="true" className="size-3.5 text-cv-accent" />
                הצעד הבא
              </span>
              {item.next_action_date == null ? null : (
                <span className="whitespace-nowrap text-cv-text-muted">
                  {formatApplicationDate(item.next_action_date)}
                  {nextActionOverdue ? " · באיחור" : null}
                </span>
              )}
            </div>
            <p className="line-clamp-2 font-semibold" dir="auto">
              {item.next_action}
            </p>
          </div>
        )}

        {attention == null ? null : (
          <Link
            className={cx(
              "mb-3 flex items-start gap-1.5 rounded-control border px-3 py-2 text-support font-semibold hover:underline",
              attention.tone === "blocker"
                ? "border-cv-blocker/30 bg-cv-blocker-soft text-cv-blocker"
                : "border-cv-warning/30 bg-cv-warning-soft text-cv-warning",
            )}
            to={`${href}/preparation`}
          >
            <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span className="line-clamp-2">{attention.label}</span>
          </Link>
        )}

        {item.notes === "" || attention != null || item.next_action != null ? null : (
          <p className="mb-3 line-clamp-2 text-support italic text-cv-text-muted" dir="auto">
            “{item.notes}”
          </p>
        )}
      </div>

      <div className="mt-2 flex items-end justify-between gap-3 border-t border-cv-border pt-3">
        <div className="flex items-center gap-1">
          <Link
            aria-label={`עדכון סטטוס ומשימות עבור ${item.company}`}
            className="inline-flex min-h-9 items-center rounded-control px-2 text-cv-text-muted transition-colors hover:bg-cv-surface-muted hover:text-cv-text"
            title="עדכון סטטוס ומשימות"
            to={`${href}/tracking`}
          >
            <SlidersHorizontal aria-hidden="true" className="size-4" />
          </Link>
          {closed ? null : (
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
          <span className="ms-1 inline-flex items-center gap-1 text-support text-cv-text-muted">
            <Clock aria-hidden="true" className="size-3.5" />
            {formatApplicationDate(item.updated_at)}
          </span>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          {reportedOperation != null ? (
            <StatusBadge className="px-2.5" tone={statusTones[reportedOperation.status]}>
              {operationTypeLabels[reportedOperation.operation_type]} · {statusLabels[reportedOperation.status]}
            </StatusBadge>
          ) : item.recommended_action == null ? null : (
            <Link
              className="inline-flex min-h-9 items-center gap-1.5 rounded-pill bg-cv-accent-soft px-3 text-support font-semibold text-cv-accent hover:bg-cv-accent hover:text-cv-on-accent"
              to={actionDestination(item.recommended_action, item.id) ?? href}
            >
              <ArrowLeft aria-hidden="true" className="size-4" />
              {actionLabel(item.recommended_action)}
            </Link>
          )}
          {reportedOperation == null && item.latest_ready_revision_id != null ? (
            <Link
              className="inline-flex items-center gap-1.5 text-support font-semibold text-cv-accent hover:underline"
              to={`/revisions/${encodeURIComponent(item.latest_ready_revision_id)}`}
            >
              <FileCheck2 aria-hidden="true" className="size-4" />
              הגרסה המוכנה
            </Link>
          ) : null}
        </div>
      </div>
    </article>
  );
};

export const ApplicationCardsView = ({ items, onRequestClose }: AlternativeViewProps) => (
  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
    {items.map((item) => (
      <ApplicationCard item={item} key={item.id} onRequestClose={onRequestClose} />
    ))}
  </div>
);

interface PipelineColumn {
  id: string;
  title: string;
  statuses: readonly string[];
  tone: "neutral" | "accent" | "warning" | "success";
}

const pipelineColumns: readonly PipelineColumn[] = [
  { id: "saved", title: "נשמרו / בהכנה", statuses: ["saved"], tone: "neutral" },
  { id: "applied", title: "הוגשו", statuses: ["applied"], tone: "accent" },
  {
    id: "screening",
    title: "סינון ומטלות",
    statuses: ["recruiter_screen", "assignment"],
    tone: "warning",
  },
  {
    id: "interviews",
    title: "ראיונות והצעות",
    statuses: ["interview", "final_stage", "offer", "accepted"],
    tone: "success",
  },
  {
    id: "closed",
    title: "תהליכים סגורים",
    statuses: ["rejected", "withdrawn", "closed"],
    tone: "neutral",
  },
];

const pipelineToneClasses: Record<PipelineColumn["tone"], string> = {
  neutral: "border-cv-border bg-cv-surface-muted",
  accent: "border-cv-accent/30 bg-cv-accent-soft/40",
  warning: "border-cv-warning/30 bg-cv-warning-soft/40",
  success: "border-cv-success/30 bg-cv-success-soft/40",
};

const PipelineCard = ({ item }: { item: ApplicationListItem }) => {
  const href = `/applications/${encodeURIComponent(item.id)}`;

  return (
    <article className="group flex flex-col gap-2.5 rounded-control border border-cv-border bg-cv-surface p-3 shadow-surface transition-all hover:border-cv-border-strong hover:shadow-floating">
      <div>
        <div className="mb-1 flex items-start justify-between gap-2">
          <Link
            className="min-w-0 truncate text-support font-extrabold text-cv-text transition-colors group-hover:text-cv-accent hover:underline"
            dir="auto"
            to={href}
          >
            {item.company}
          </Link>
          {item.fit_level == null ? null : (
            <span className="shrink-0 text-support font-semibold text-cv-accent">{fitLevelLabel(item.fit_level)}</span>
          )}
        </div>
        <p className="mb-2 truncate text-support text-cv-text-muted" dir="auto" title={item.target_role}>
          {item.target_role}
        </p>
        <StatusBadge
          className="px-2 py-0.5"
          icon={preparationStateIcons[item.preparation_state]}
          tone={preparationStateTones[item.preparation_state]}
        >
          {preparationStateLabels[item.preparation_state]}
        </StatusBadge>
        {item.next_action == null ? null : (
          <p className="mt-2 line-clamp-2 rounded-control bg-cv-surface-muted px-2 py-1.5 text-support text-cv-text-muted">
            <strong className="text-cv-text">הבא: </strong>
            <span dir="auto">{item.next_action}</span>
          </p>
        )}
      </div>
      <div className="flex items-center justify-between gap-2 border-t border-cv-border pt-2 text-support">
        <Link className="font-semibold text-cv-text-muted hover:text-cv-text hover:underline" to={`${href}/tracking`}>
          פרטים ומשימה
        </Link>
        <span className="text-cv-text-muted">{recruitmentStatusLabel(item.recruitment_status)}</span>
      </div>
    </article>
  );
};

export const ApplicationPipelineView = ({ items }: AlternativeViewProps) => {
  const knownStatuses = new Set(pipelineColumns.flatMap((column) => column.statuses));
  const unknownStatuses = [...new Set(items.map((item) => item.recruitment_status))].filter(
    (status) => !knownStatuses.has(status),
  );
  const populatedOrActiveColumns = pipelineColumns.filter(
    (column) => column.id !== "closed" || items.some((item) => column.statuses.includes(item.recruitment_status)),
  );
  const columns: readonly PipelineColumn[] =
    unknownStatuses.length === 0
      ? populatedOrActiveColumns
      : [...populatedOrActiveColumns, { id: "other", title: "שלב אחר", statuses: unknownStatuses, tone: "neutral" }];

  return (
    <div
      aria-label="מועמדויות לפי שלב גיוס"
      className="grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-4"
      role="list"
    >
      {columns.map((column) => {
        const stageItems = items.filter((item) => column.statuses.includes(item.recruitment_status));

        return (
          <section
            className={cx(
              "flex min-h-96 flex-col rounded-surface border p-3 shadow-surface",
              pipelineToneClasses[column.tone],
            )}
            key={column.id}
            role="listitem"
          >
            <div className="mb-2 flex items-center justify-between gap-3 border-b border-cv-border px-1 pb-2.5">
              <h2 className="text-support font-extrabold text-cv-text">{column.title}</h2>
              <span className="rounded-pill border border-cv-border bg-cv-surface px-2 py-0.5 text-support font-bold text-cv-text">
                {stageItems.length}
              </span>
            </div>
            {stageItems.length === 0 ? (
              <div className="flex h-28 items-center justify-center rounded-control border border-dashed border-cv-border bg-cv-surface/40 px-3 text-center text-support text-cv-text-muted">
                אין מועמדויות בשלב זה
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {stageItems.map((item) => (
                  <PipelineCard item={item} key={item.id} />
                ))}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
};
