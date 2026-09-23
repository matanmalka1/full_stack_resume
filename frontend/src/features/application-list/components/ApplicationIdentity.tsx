import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { sourceHostname } from "@/features/applications";
import { preparationResumeDestination, trackLabel } from "@/features/preparation";
import { cx } from "@/ui/cx";
import type { ApplicationListViewVariant } from "../model/applicationList.types";
import { formatApplicationDate } from "../model/applicationListPresentation";

/* The first letter of the first two words - "Check Point" is CP, "Wiz" is W - so the
   mark reads as the company's initials rather than as a truncated word. */
const companyInitials = (company: string): string =>
  company
    .split(/\s+/)
    .filter((word) => word !== "")
    .slice(0, 2)
    .map((word) => [...word][0])
    .join("")
    .toLocaleUpperCase() || "?";

export const CompanyMark = ({ company, variant }: { company: string; variant: "card" | "row" }) => (
  <span
    aria-hidden="true"
    className={cx(
      "flex shrink-0 items-center justify-center rounded-control bg-cv-accent-soft text-support text-cv-accent",
      variant === "row"
        ? "size-9 border border-cv-border font-bold"
        : "size-11 border border-cv-accent/20 font-extrabold shadow-surface",
    )}
  >
    {companyInitials(company)}
  </span>
);

/* The card's third line: the track and where the posting came from, as plain text. */
const ApplicationProvenance = ({ item }: { item: ApplicationListItem }) => {
  const host = sourceHostname(item.source_url);
  const origin = host ?? (item.source === "manual" ? null : item.source);
  if (item.track == null && origin == null) return null;

  return (
    <p className="truncate text-support text-cv-text-muted">
      {item.track == null ? null : trackLabel(item.track)}
      {item.track != null && origin != null ? " · " : null}
      {origin}
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

  if (variant === "row") {
    return <RowIdentity ambiguous={ambiguous} href={href} item={item} />;
  }

  /* The card leads with the company, beside its mark, and names the role under it. */
  return (
    <div className="flex min-w-0 items-center gap-3">
      <CompanyMark company={item.company} variant={variant} />
      <div className="min-w-0 text-left">
        <Link
          className="block truncate font-extrabold text-cv-text transition-colors group-hover:text-cv-accent hover:underline"
          dir="auto"
          title={item.company}
          to={href}
        >
          {item.company}
        </Link>
        <p className="truncate text-support font-medium text-cv-text-muted" dir="auto" title={item.target_role}>
          {item.target_role}
        </p>
        <ApplicationProvenance item={item} />
      </div>
    </div>
  );
};

/* The table row's identity, drawn after demo_re: the company on the first line with
   the row's link beside it, the role and the track on the second.

   The name is text; the icon is the link. It is on every row and is a real anchor, so it
   stays the keyboard and screen-reader route into the Application and still opens a new
   tab on Cmd/Ctrl-click. The posting's own address is in the row's menu. */
const RowIdentity = ({ ambiguous, href, item }: { ambiguous: boolean; href: string; item: ApplicationListItem }) => (
  <div className="flex min-w-0 items-center gap-3">
    <CompanyMark company={item.company} variant="row" />
    <div className="min-w-0 flex-1">
      <div className="flex min-w-0 items-center gap-1.5">
        <span
          className="truncate text-body font-bold text-cv-text transition-colors group-hover:text-cv-accent"
          dir="auto"
          title={item.company}
        >
          {item.company}
        </span>
        <Link
          aria-label={`פתיחת המועמדות של ${item.company}`}
          className="inline-flex shrink-0 rounded-control p-0.5 text-cv-text-muted hover:text-cv-text"
          title="פתיחת המועמדות"
          to={href}
        >
          <ExternalLink aria-hidden="true" className="size-icon-sm" />
        </Link>
      </div>
      <p className="flex min-w-0 items-center gap-1.5 text-support text-cv-text-muted">
        <span className="truncate font-medium text-cv-text" dir="auto" title={item.target_role}>
          {item.target_role}
        </span>
        {item.track == null ? null : (
          <>
            <span aria-hidden="true">·</span>
            <span className="shrink-0">{trackLabel(item.track)}</span>
          </>
        )}
      </p>
      {ambiguous ? (
        <p className="truncate text-support font-medium text-cv-text" title={DUPLICATE_IDENTITY_HINT}>
          {DUPLICATE_IDENTITY_HINT} · נפתחה ב־{formatApplicationDate(item.created_at)}
        </p>
      ) : null}
    </div>
  </div>
);
