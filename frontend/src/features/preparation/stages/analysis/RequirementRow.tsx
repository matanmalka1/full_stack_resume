import {
  Check,
  CircleAlert,
  CircleHelp,
  CircleX,
  FileCheck2,
  type LucideIcon,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { type ReactNode, useState } from "react";

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

/* Every part of the disclosure has the same shape: an optional caption, then its body.
   Bodies keep the page's inline start - the English text is isolated in <bdi> inside an
   RTL block, never made a block of its own, which would flip it to the opposite edge. */
const DetailSection = ({
  children,
  icon: Icon,
  iconClassName,
  title,
}: {
  children: ReactNode;
  icon: LucideIcon;
  iconClassName: string;
  title: string | null;
}) => (
  <div className="flex flex-col gap-2">
    {title === null ? null : (
      <p className="flex items-center gap-1.5 text-caption font-semibold text-cv-text-muted">
        <Icon aria-hidden="true" className={cx("size-icon-sm", iconClassName)} />
        {title}
      </p>
    )}
    {children}
  </div>
);

const FactList = ({ children }: { children: ReactNode }) => (
  <ul className="flex flex-col gap-2 text-support leading-6 text-cv-text">{children}</ul>
);

/* Only an omission is worth a word: a cited fact is expected to be in the CV. */
const EvidenceFact = ({ factId, evidence }: { evidence: RequirementEvidence; factId: string }) => (
  <li>
    <bdi>{evidence.label(factId)}</bdi>
    {evidence.inclusion(factId) === "omitted" ? (
      <span className="block text-caption font-semibold text-cv-warning">לא נבחרה לקורות החיים</span>
    ) : null}
  </li>
);

/* A fact cited on an uncovered requirement did not establish it, so it is described as
   checked against the requirement rather than as evidence for it. */
const evidenceSummary = (supporting: number, cited: number, matched: boolean) =>
  supporting === 0
    ? cited > 0
      ? "מה מגביל את הכיסוי"
      : "הסבר ה-AI"
    : matched
      ? supporting === 1
        ? "עובדה אחת מעידה על הדרישה"
        : `${supporting} עובדות מעידות על הדרישה`
      : supporting === 1
        ? "עובדה אחת נבדקה מול הדרישה"
        : `${supporting} עובדות נבדקו מול הדרישה`;

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
  /* The disclosure's summary already names what leads it (the supporting facts, or the
     rationale when nothing is cited); captions are needed only to tell parts apart. */
  const captioned = [
    requirement.supportingFactIds.length,
    requirement.boundaryFactIds.length,
    detailRationale === null ? 0 : 1,
  ].filter((count) => count > 0).length > 1;

  return (
    <li className="flex flex-col gap-2 py-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <h4 className={cx("min-w-0 flex-1 text-body font-semibold", matched ? "text-cv-text-muted" : "text-cv-text")}>
          <bdi>{requirement.text}</bdi>
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
        <p className="text-support leading-6 text-cv-text-muted">
          <span className="font-semibold text-cv-text">הסבר ה-AI: </span>
          <bdi>{rationale}</bdi>
        </p>
      )}

      {shortfall === null ? null : (
        <p className={cx("ps-3 text-support leading-6 text-cv-text-muted", shortfallRules[severity])}>
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
            {evidenceSummary(requirement.supportingFactIds.length, citedCount, matched)}
          </DisclosureSummary>
          <div className="mt-2 flex flex-col gap-4 rounded-control bg-cv-surface-muted p-3">
            {detailRationale === null ? null : (
              <DetailSection
                icon={Sparkles}
                iconClassName="text-cv-text-muted"
                title={captioned ? "הסבר ה-AI" : null}
              >
                <p className="text-support leading-6 text-cv-text">
                  <bdi>{detailRationale}</bdi>
                </p>
              </DetailSection>
            )}
            {requirement.supportingFactIds.length === 0 ? null : (
              <DetailSection
                icon={FileCheck2}
                iconClassName="text-cv-success"
                title={captioned ? (matched ? "ראיות תומכות" : "עובדות שנבדקו") : null}
              >
                <FactList>
                  {requirement.supportingFactIds.map((factId) => (
                    <EvidenceFact evidence={evidence} factId={factId} key={factId} />
                  ))}
                </FactList>
              </DetailSection>
            )}
            {requirement.boundaryFactIds.length === 0 ? null : (
              <DetailSection
                icon={ShieldAlert}
                iconClassName="text-cv-warning"
                title={captioned ? "עובדות שמגבילות את הכיסוי" : null}
              >
                <FactList>
                  {requirement.boundaryFactIds.map((factId) => (
                    <li key={factId}>
                      <bdi>{evidence.label(factId)}</bdi>
                    </li>
                  ))}
                </FactList>
              </DetailSection>
            )}
          </div>
        </details>
      )}
    </li>
  );
};
