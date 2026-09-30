import { Check, CircleAlert, CircleHelp, CircleX, FileCheck2, type LucideIcon, ShieldAlert } from "lucide-react";
import { useState } from "react";

import type { Requirement, RequirementCoverage, ShortfallSeverity } from "@/api/analyses";
import { DisclosureSummary } from "@/ui/Disclosure";
import { StatusBadge } from "@/ui/StatusBadge";
import { cx } from "@/ui/cx";
import { coverageLabels, coverageTones } from "../../model/analysisLabels";
import type { RequirementEvidence } from "./useRequirementEvidence";

const shortfallLabels: Record<ShortfallSeverity, string> = {
  none: "אין פער",
  minor: "פער קטן",
  material: "פער מהותי",
  unknown: "חומרת הפער לא הוכרעה",
};

/* The palette is greyscale, so severity is carried by the rule's weight rather than its
   hue: a material gap draws the heaviest, darkest line beside its explanation. */
const shortfallRules: Record<ShortfallSeverity, string> = {
  none: "border-s-2 border-cv-border",
  minor: "border-s-2 border-cv-warning",
  material: "border-s-4 border-cv-blocker",
  unknown: "border-s-2 border-dashed border-cv-border-strong",
};

/* One mark per coverage state, carried by the badge. The row used to draw a second,
   bare icon at its inline start that repeated the badge without its word. */
const coverageIcons: Record<RequirementCoverage, LucideIcon> = {
  matched: Check,
  partial: CircleAlert,
  unsupported: CircleX,
  unknown: CircleHelp,
};

/* Only an omission is worth a word: a cited fact is expected to be in the CV. */
const EvidenceFact = ({ factId, evidence }: { evidence: RequirementEvidence; factId: string }) => (
  <li className="flex flex-col gap-0.5">
    <bdi className="text-support text-cv-text">{evidence.label(factId)}</bdi>
    {evidence.inclusion(factId) === "omitted" ? (
      <span className="text-caption font-semibold text-cv-warning">לא נבחרה לקורות החיים</span>
    ) : null}
  </li>
);

const evidenceSummary = (supporting: number, cited: number) =>
  supporting === 1
    ? "עובדה אחת מעידה על הדרישה"
    : supporting > 1
      ? `${supporting} עובדות מעידות על הדרישה`
      : cited > 0
        ? "מה מגביל את הכיסוי"
        : "הסבר ה-AI";

export const RequirementRow = ({
  evidence,
  gapReason,
  requirement,
}: {
  evidence: RequirementEvidence;
  gapReason: string | undefined;
  requirement: Requirement;
}) => {
  const [open, setOpen] = useState(false);
  const matched = requirement.coverage === "matched";
  const citedCount = requirement.supportingFactIds.length + requirement.boundaryFactIds.length;
  const severity = requirement.shortfallSeverity ?? "unknown";
  /* One explanation on the row. A covered requirement shows why it is covered; an uncovered
     one shows its shortfall, falling back to the rationale or the gap's reason, and shows
     no line at all when none was given. A rationale the shortfall displaced is kept behind
     the row's disclosure rather than dropped. */
  const shortfall = matched ? null : (requirement.shortfallReason ?? requirement.rationale ?? gapReason ?? null);
  const rationale = matched ? requirement.rationale : null;
  const detailRationale = !matched && shortfall !== requirement.rationale ? requirement.rationale : null;

  return (
    <li className="flex flex-col gap-2 py-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <h4
          className={cx("min-w-0 flex-1 text-body font-semibold", matched ? "text-cv-text-muted" : "text-cv-text")}
          dir="auto"
        >
          {requirement.text}
        </h4>
        <StatusBadge
          className="shrink-0"
          icon={coverageIcons[requirement.coverage]}
          tone={coverageTones[requirement.coverage]}
        >
          {coverageLabels[requirement.coverage]}
        </StatusBadge>
      </div>

      {rationale === null ? null : (
        <p className="text-support leading-6 text-cv-text-muted" dir="auto">
          <span className="font-semibold text-cv-text">הסבר ה-AI: </span>
          <bdi>{rationale}</bdi>
        </p>
      )}

      {shortfall === null ? null : (
        <p className={cx("ps-3 text-support leading-6 text-cv-text-muted", shortfallRules[severity])} dir="auto">
          <span className="font-semibold text-cv-text">{shortfallLabels[severity]}: </span>
          <bdi>{shortfall}</bdi>
        </p>
      )}

      {citedCount === 0 && detailRationale === null ? null : (
        <details onToggle={(event) => setOpen(event.currentTarget.open)}>
          <DisclosureSummary
            className="w-fit text-support font-medium text-cv-text-muted transition-colors hover:text-cv-text"
            open={open}
          >
            {evidenceSummary(requirement.supportingFactIds.length, citedCount)}
          </DisclosureSummary>
          <div className="mt-2 flex flex-col gap-4 rounded-control bg-cv-surface-muted p-3">
            {detailRationale === null ? null : (
              <p className="text-support leading-6 text-cv-text-muted" dir="auto">
                <span className="font-semibold text-cv-text">הסבר ה-AI: </span>
                <bdi>{detailRationale}</bdi>
              </p>
            )}
            {requirement.supportingFactIds.length === 0 ? null : (
              <div>
                <p className="mb-2 flex items-center gap-1.5 text-caption font-semibold text-cv-text-muted">
                  <FileCheck2 aria-hidden="true" className="size-icon-sm text-cv-success" />
                  ראיות תומכות
                </p>
                <ul className="flex flex-col gap-2.5">
                  {requirement.supportingFactIds.map((factId) => (
                    <EvidenceFact evidence={evidence} factId={factId} key={factId} />
                  ))}
                </ul>
              </div>
            )}
            {requirement.boundaryFactIds.length === 0 ? null : (
              <div>
                <p className="mb-2 flex items-center gap-1.5 text-caption font-semibold text-cv-text-muted">
                  <ShieldAlert aria-hidden="true" className="size-icon-sm text-cv-warning" />
                  עובדות שמגבילות את הכיסוי
                </p>
                <ul className="flex flex-col gap-2.5">
                  {requirement.boundaryFactIds.map((factId) => (
                    <li className="text-support text-cv-text" key={factId}>
                      <bdi>{evidence.label(factId)}</bdi>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </details>
      )}
    </li>
  );
};
