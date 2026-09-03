import { Clock } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "../../api/contracts";
import { appRoutes } from "../../app/appRoutes";
import { StatusBadge } from "../../ui/StatusBadge";
import { cx } from "../../ui/cx";
import { trackLabel } from "../application/analysisLabels";
import { preparationStateIcons, preparationStateLabels, preparationStateTones } from "../application/applicationLabels";
import { sourceHostname } from "../application/applicationPresentation";
import { formatApplicationDate, isNextActionOverdue } from "./applicationListPresentation";

export type ApplicationListViewVariant = "card" | "pipeline" | "row";

export const CompanyMark = ({ company, variant }: { company: string; variant: "card" | "row" }) => (
  <span
    aria-hidden="true"
    className={cx(
      "flex shrink-0 items-center justify-center rounded-control bg-cv-accent-soft text-support text-cv-accent",
      variant === "row" ? "size-9 font-bold" : "size-11 border border-cv-accent/20 font-extrabold shadow-surface",
    )}
  >
    {variant === "row" ? ([...company][0] ?? "?") : [...company].slice(0, 2).join("").toLocaleUpperCase() || "?"}
  </span>
);

export const ApplicationProvenance = ({
  item,
  linkSource = false,
}: {
  item: ApplicationListItem;
  linkSource?: boolean;
}) => {
  const host = sourceHostname(item.source_url);
  const origin = host ?? (item.source === "manual" ? null : item.source);

  if (item.track == null && origin == null) {
    return null;
  }

  return (
    <p className="truncate text-support text-cv-text-muted">
      {item.track == null ? null : trackLabel(item.track)}
      {item.track != null && origin != null ? " · " : null}
      {origin === null ? null : linkSource && host !== null && item.source_url != null ? (
        <a
          className="hover:underline"
          dir="ltr"
          href={item.source_url}
          rel="noreferrer"
          target="_blank"
          title={item.source_url}
        >
          {host}
        </a>
      ) : (
        origin
      )}
    </p>
  );
};

const DUPLICATE_IDENTITY_HINT = "קיימת עוד מועמדות לאותה חברה ולאותו תפקיד";

export const ApplicationIdentity = ({
  afterCompany,
  ambiguous = false,
  item,
  variant,
}: {
  afterCompany?: ReactNode;
  ambiguous?: boolean;
  item: ApplicationListItem;
  variant: ApplicationListViewVariant;
}) => {
  const href = appRoutes.application(item.id);

  if (variant === "pipeline") {
    return (
      <>
        <div className="mb-1 flex items-start justify-between gap-2">
          <Link
            className="min-w-0 truncate text-support font-extrabold text-cv-text transition-colors group-hover:text-cv-accent hover:underline"
            dir="auto"
            to={href}
          >
            {item.company}
          </Link>
          {afterCompany}
        </div>
        <p className="mb-2 truncate text-support text-cv-text-muted" dir="auto" title={item.target_role}>
          {item.target_role}
        </p>
      </>
    );
  }

  const row = variant === "row";

  return (
    <div className={row ? "flex min-w-0 items-start gap-2" : "flex min-w-0 items-center gap-3"}>
      <CompanyMark company={item.company} variant={variant} />
      <div className={cx("min-w-0 text-left", row && "flex-1")}>
        <Link
          className={
            row
              ? "block truncate text-support font-bold text-cv-text hover:underline"
              : "block truncate font-extrabold text-cv-text transition-colors group-hover:text-cv-accent hover:underline"
          }
          dir="auto"
          to={href}
        >
          {item.company}
        </Link>
        <p className="truncate text-support text-cv-text-muted" dir="auto" title={row ? undefined : item.target_role}>
          {item.target_role}
        </p>
        <ApplicationProvenance item={item} linkSource={row} />
        {row && ambiguous ? (
          <p className="truncate text-support font-medium text-cv-text" title={DUPLICATE_IDENTITY_HINT}>
            {DUPLICATE_IDENTITY_HINT} · נפתחה ב־{formatApplicationDate(item.created_at)}
          </p>
        ) : null}
      </div>
    </div>
  );
};

export const ApplicationPreparationBadge = ({
  item,
  variant,
}: {
  item: ApplicationListItem;
  variant: ApplicationListViewVariant;
}) => (
  <StatusBadge
    className={variant === "row" ? "gap-1.5 px-2.5 text-start" : variant === "card" ? "px-2.5 py-0.5" : "px-2 py-0.5"}
    icon={preparationStateIcons[item.preparation_state]}
    tone={preparationStateTones[item.preparation_state]}
  >
    {preparationStateLabels[item.preparation_state]}
  </StatusBadge>
);

export const ApplicationNextAction = ({
  closed = false,
  item,
  variant,
}: {
  closed?: boolean;
  item: ApplicationListItem;
  variant: ApplicationListViewVariant;
}) => {
  if (variant === "row") {
    if (item.next_action == null) {
      return (
        <span className="text-support text-cv-text-muted" title="לא נקבעה משימת גיוס">
          —
        </span>
      );
    }

    const overdue = isNextActionOverdue(item.next_action_date);
    return (
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
    );
  }

  if (item.next_action == null) {
    return null;
  }

  if (variant === "pipeline") {
    return (
      <p className="mt-2 line-clamp-2 rounded-control bg-cv-surface-muted px-2 py-1.5 text-support text-cv-text-muted">
        <strong className="text-cv-text">הבא: </strong>
        <span dir="auto">{item.next_action}</span>
      </p>
    );
  }

  const overdue = !closed && isNextActionOverdue(item.next_action_date);
  return (
    <div
      className={cx(
        "mb-3 rounded-control border px-3 py-2 text-support",
        overdue
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
            {overdue ? " · באיחור" : null}
          </span>
        )}
      </div>
      <p className="line-clamp-2 font-semibold" dir="auto">
        {item.next_action}
      </p>
    </div>
  );
};
