import { Check, CircleAlert, CircleHelp, FileCheck2, type LucideIcon, ShieldAlert } from "lucide-react";
import { useState } from "react";

import type { Requirement, RequirementCoverage, ShortfallSeverity } from "@/api/analyses";
import { DisclosureSummary } from "@/ui/Disclosure";
import { StatusBadge } from "@/ui/StatusBadge";
import { cx } from "@/ui/cx";
import { coverageLabels, coverageTones } from "../../model/analysisLabels";
import type { EvidenceInclusion, RequirementEvidence } from "./useRequirementEvidence";

const shortfallLabels: Record<ShortfallSeverity, string> = {
  none: "אין פער",
  minor: "פער קטן",
  material: "פער מהותי",
  unknown: "חומרת הפער לא הוכרעה",
};

const coverageMarks: Record<RequirementCoverage, { className: string; icon: LucideIcon }> = {
  matched: { className: "bg-cv-success-soft text-cv-success", icon: Check },
  partial: { className: "bg-cv-warning-soft text-cv-warning", icon: CircleAlert },
  unsupported: { className: "bg-cv-blocker-soft text-cv-blocker", icon: CircleAlert },
  unknown: { className: "bg-cv-surface-muted text-cv-text-muted", icon: CircleHelp },
};

const inclusionLabels: Record<EvidenceInclusion, string | null> = {
  included: "בקורות החיים",
  omitted: "לא נבחרה לקורות החיים",
  unknown: null,
};

const EvidenceFact = ({ factId, evidence }: { evidence: RequirementEvidence; factId: string }) => {
  const inclusion = evidence.inclusion(factId);
  const label = inclusionLabels[inclusion];
  return (
    <li className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
      <bdi className="min-w-0 flex-1 text-support text-cv-text">{evidence.label(factId)}</bdi>
      {label === null ? null : (
        <span
          className={cx(
            "shrink-0 rounded-pill px-2 py-0.5 text-caption font-semibold",
            inclusion === "included" ? "bg-cv-success-soft text-cv-success" : "bg-cv-warning-soft text-cv-warning",
          )}
        >
          {label}
        </span>
      )}
    </li>
  );
};

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
  const mark = coverageMarks[requirement.coverage];
  const Icon = mark.icon;
  const matched = requirement.coverage === "matched";
  const citedCount = requirement.supportingFactIds.length + requirement.boundaryFactIds.length;
  const shortfall = matched ? null : (requirement.shortfallReason ?? gapReason ?? "לא סופק הסבר מפורט לפער.");

  return (
    <li className="flex items-start gap-3 py-3">
      <span className={cx("mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-pill", mark.className)}>
        <Icon aria-hidden="true" className="size-icon-sm" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
          <h4 className="min-w-0 flex-1 text-body font-semibold text-cv-text" dir="auto">
            {requirement.text}
          </h4>
          <StatusBadge className="shrink-0" tone={coverageTones[requirement.coverage]}>
            {coverageLabels[requirement.coverage]}
          </StatusBadge>
        </div>

        {shortfall === null ? null : (
          <p className="mt-1 text-support text-cv-text-muted" dir="auto">
            <span className="font-semibold text-cv-text">
              {shortfallLabels[requirement.shortfallSeverity ?? "unknown"]}:{" "}
            </span>
            <bdi>{shortfall}</bdi>
          </p>
        )}

        {citedCount === 0 ? null : (
          <details className="mt-1.5" onToggle={(event) => setOpen(event.currentTarget.open)}>
            <DisclosureSummary className="text-support font-medium text-cv-text-muted hover:text-cv-text" open={open}>
              {requirement.supportingFactIds.length === 1
                ? "עובדה אחת מעידה על הדרישה"
                : requirement.supportingFactIds.length > 1
                  ? `${requirement.supportingFactIds.length} עובדות מעידות על הדרישה`
                  : "מה מגביל את הכיסוי"}
            </DisclosureSummary>
            <div className="mt-2 flex flex-col gap-3 border-s-2 border-cv-border ps-3">
              {requirement.supportingFactIds.length === 0 ? null : (
                <div>
                  <p className="mb-1 flex items-center gap-1.5 text-caption font-semibold text-cv-text-muted">
                    <FileCheck2 aria-hidden="true" className="size-icon-sm text-cv-success" />
                    ראיות תומכות
                  </p>
                  <ul className="flex flex-col gap-1.5">
                    {requirement.supportingFactIds.map((factId) => (
                      <EvidenceFact evidence={evidence} factId={factId} key={factId} />
                    ))}
                  </ul>
                </div>
              )}
              {requirement.boundaryFactIds.length === 0 ? null : (
                <div>
                  <p className="mb-1 flex items-center gap-1.5 text-caption font-semibold text-cv-text-muted">
                    <ShieldAlert aria-hidden="true" className="size-icon-sm text-cv-warning" />
                    עובדות שמגבילות את הכיסוי
                  </p>
                  <ul className="flex flex-col gap-1.5">
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
      </div>
    </li>
  );
};
