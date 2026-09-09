import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { sourceHostname } from "@/features/applications";
import { preparationResumeDestination, trackLabel } from "@/features/preparation";
import { cx } from "@/ui/cx";
import type { ApplicationListViewVariant } from "../model/applicationList.types";
import { formatApplicationDate } from "../model/applicationListPresentation";

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

const ApplicationProvenance = ({ item, linkSource }: { item: ApplicationListItem; linkSource: boolean }) => {
  const host = sourceHostname(item.source_url);
  const origin = host ?? (item.source === "manual" ? null : item.source);
  if (item.track == null && origin == null) return null;

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
  const href = preparationResumeDestination(item);
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
              ? "block truncate text-body font-bold text-cv-text transition-colors group-hover:text-cv-accent hover:underline"
              : "block truncate font-extrabold text-cv-text transition-colors group-hover:text-cv-accent hover:underline"
          }
          dir="auto"
          title={row ? item.target_role : item.company}
          to={href}
        >
          {row ? item.target_role : item.company}
        </Link>
        <p
          className="truncate text-support font-medium text-cv-text-muted"
          dir="auto"
          title={row ? item.company : item.target_role}
        >
          {row ? item.company : item.target_role}
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
