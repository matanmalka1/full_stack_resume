import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { preparationResumeDestination, trackLabel } from "@/features/preparation";
import { Tooltip } from "@/ui/Tooltip";
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

export const CompanyMark = ({ company }: { company: string }) => (
  <span
    aria-hidden="true"
    className="flex size-9 shrink-0 items-center justify-center rounded-control border border-cv-border bg-cv-accent-soft text-support font-bold text-cv-accent"
  >
    {companyInitials(company)}
  </span>
);

const DUPLICATE_IDENTITY_HINT = "קיימת עוד מועמדות לאותה חברה ולאותו תפקיד";

/* "row" is the identity the table and the cards draw, after demo_re: the company on the
   first line with the record's link beside it, the role and the track on the second.

   The name is text; the icon is the link. It is on every record and is a real anchor, so
   it stays the keyboard and screen-reader route into the Application and still opens a
   new tab on Cmd/Ctrl-click. The posting's own address is in the record's menu.

   "pipeline" is the stage card's: the company as its link, with whatever the caller
   hangs beside it, and the role under it. */
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
      <div>
        <div className="mb-1 flex items-start justify-between gap-2">
          <Link
            className="min-w-0 truncate text-support font-bold text-cv-text transition-colors group-hover:text-cv-accent hover:underline"
            dir="auto"
            to={href}
          >
            {item.company}
          </Link>
          {afterCompany}
        </div>
        <p className="line-clamp-2 text-support text-cv-text-muted" dir="auto">
          {item.target_role}
        </p>
      </div>
    );
  }

  return (
    <div className="flex min-w-0 items-center gap-3">
      <CompanyMark company={item.company} />
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-1.5">
          <span
            className="truncate text-body font-bold text-cv-text transition-colors group-hover:text-cv-accent"
            dir="auto"
          >
            {item.company}
          </span>
          <Tooltip label="פתיחת המועמדות">
            <Link
              aria-label={`פתיחת המועמדות של ${item.company}`}
              className="inline-flex shrink-0 rounded-control p-0.5 text-cv-text-muted hover:text-cv-text"
              to={href}
            >
              <ExternalLink aria-hidden="true" className="size-icon-sm" />
            </Link>
          </Tooltip>
        </div>
        {/* Clamped rather than truncated: with no tooltip on it, a long role must still be
            readable in full within two lines. */}
        <p className="flex min-w-0 items-baseline gap-1.5 text-support text-cv-text-muted">
          <span className="line-clamp-2 min-w-0 font-medium text-cv-text" dir="auto">
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
          <p className="line-clamp-2 text-support font-medium text-cv-text">
            {DUPLICATE_IDENTITY_HINT} · נפתחה ב־{formatApplicationDate(item.created_at)}
          </p>
        ) : null}
      </div>
    </div>
  );
};
