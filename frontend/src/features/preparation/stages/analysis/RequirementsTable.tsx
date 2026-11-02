import { Check, ChevronDown, CircleAlert, CircleHelp, Contrast, type LucideIcon } from "lucide-react";
import { useState } from "react";

import type { Requirement, RequirementCoverage, RequirementImportance, ShortfallSeverity } from "@/api/analyses";
import { FilterChip } from "@/ui/FilterChip";
import { cardClasses } from "@/ui/surface";
import { cx } from "@/ui/cx";
import { RequirementFactAction } from "../../components/RequirementFactAction";
import { coverageLabels } from "../../model/analysisLabels";
import type { RequirementGroup } from "../../model/requirementGroups";

const importanceLabels: Record<RequirementImportance, string> = {
  mandatory: "דרישות חובה",
  preferred: "דרישות מועדפות",
  unknown: "דרישות ללא חשיבות מוצהרת",
};

const shortfallLabels: Record<ShortfallSeverity, string> = {
  none: "אין פער",
  minor: "פער קטן",
  material: "פער מהותי",
  unknown: "חומרת הפער לא הוכרעה",
};

/* Coverage as a scale in shape as well as words: a covered requirement is a filled pill, a
   partial one a soft pill, an uncovered one a dashed outline, and one the engine could not
   decide a plain outline - so the palette's greys are never the only signal (A.2). */
const coverageBadgeClasses: Record<RequirementCoverage, string> = {
  matched: "border-cv-accent bg-cv-accent text-cv-on-accent",
  partial: "border-transparent bg-cv-surface-muted text-cv-text",
  unsupported: "border-dashed border-cv-text-muted text-cv-text",
  unknown: "border-cv-border-soft text-cv-text-muted",
};

/* The rows read down the scale, covered first, the way the design lists them: the table
   is the picture of the match, and the column beside it already gathers what falls short. */
const coverageOrder: Record<RequirementCoverage, number> = { matched: 0, partial: 1, unsupported: 2, unknown: 3 };

const coverageIcons: Record<RequirementCoverage, LucideIcon> = {
  matched: Check,
  partial: Contrast,
  unsupported: CircleAlert,
  unknown: CircleHelp,
};

const CoverageBadge = ({ coverage, icon = false }: { coverage: RequirementCoverage; icon?: boolean }) => {
  const Icon = coverageIcons[coverage];
  return (
    <span
      className={cx(
        "inline-flex shrink-0 items-center gap-1 rounded-pill border px-2 py-0.5 text-caption font-bold whitespace-nowrap",
        coverageBadgeClasses[coverage],
      )}
    >
      {icon ? <Icon aria-hidden="true" className="size-3.5 shrink-0" /> : null}
      {coverageLabels[coverage]}
    </span>
  );
};

/* The gap a requirement leaves, in the engine's own grading. A covered requirement has
   none by definition, whatever the record carries. */
const gapText = (requirement: Requirement): string =>
  requirement.coverage === "matched"
    ? shortfallLabels.none
    : shortfallLabels[requirement.shortfallSeverity ?? "unknown"];

/* What the cited facts amount to. A fact cited on an uncovered requirement did not
   establish it, so it is described as checked against the requirement rather than as
   evidence for it. Null when nothing is cited. */
const evidenceText = (requirement: Requirement): string | null => {
  const count = requirement.supportingFactIds.length;
  if (count === 0) return null;
  if (requirement.coverage === "matched") {
    return count === 1 ? "עובדה אחת מעידה על הדרישה" : `${count} עובדות מעידות על הדרישה`;
  }
  return count === 1 ? "עובדה אחת נבדקה מול הדרישה" : `${count} עובדות נבדקו מול הדרישה`;
};

/* Why coverage stops where it does, for a requirement that is not fully covered: the
   shortfall the engine stated, else the provider's account, else the gap's own reason. */
export const limitText = (requirement: Requirement, gapReason: string | undefined): string | null =>
  requirement.coverage === "matched"
    ? null
    : (requirement.shortfallReason ??
      (requirement.rationale === null ? null : `הסבר ה-AI: ${requirement.rationale}`) ??
      gapReason ??
      null);

/* A requirement no fact supports offers to record one, in the row that names it: the
   ordinary fact form, writing a pending fact (§17). The Profile picks its default file. */
const factActionFor = (requirement: Requirement, profile: string | null) =>
  requirement.supportingFactIds.length === 0 ? (
    <RequirementFactAction profile={profile} requirement={requirement} />
  ) : null;

const PhoneRow = ({
  gapReason,
  profile,
  requirement,
}: {
  gapReason: string | undefined;
  profile: string | null;
  requirement: Requirement;
}) => {
  const [open, setOpen] = useState(false);
  const evidence = evidenceText(requirement);
  const limit = limitText(requirement, gapReason);
  const material = requirement.coverage !== "matched" && requirement.shortfallSeverity === "material";

  return (
    <li className="flex flex-col gap-2 p-3.5 not-first:border-t not-first:border-cv-canvas">
      <div className="flex items-start justify-between gap-2.5">
        <bdi className="min-w-0 text-body leading-snug font-bold text-cv-text">{requirement.text}</bdi>
        <CoverageBadge coverage={requirement.coverage} icon />
      </div>
      <p className="text-support text-cv-text-muted">
        <span className={cx(material && "font-bold text-cv-text")}>{gapText(requirement)}</span>
        {evidence === null ? null : ` · ${evidence}`}
      </p>
      {limit === null ? null : (
        <details className="text-support" onToggle={(event) => setOpen(event.currentTarget.open)}>
          <summary className="flex min-h-8 w-fit cursor-pointer list-none items-center gap-1 font-bold text-cv-text [&::-webkit-details-marker]:hidden">
            מה מגביל את הכיסוי
            <ChevronDown aria-hidden="true" className={cx("size-icon-sm transition-transform", open && "rotate-180")} />
          </summary>
          <p className="mt-1 leading-relaxed text-cv-text-muted">
            <bdi>{limit}</bdi>
          </p>
        </details>
      )}
      {factActionFor(requirement, profile)}
    </li>
  );
};

/* The requirements the analysis read from the posting, one importance at a time - the
   group the reader picks from the chips above - and how far the facts cover each.

   A phone lists them as rows, the explanation of a shortfall folded under each; a wide
   screen draws one table and leaves the explanations to the column beside it. The group
   is the caller's, so that column explains the same rows the table shows. */
export const RequirementsTable = ({
  active,
  gapReasons,
  groups,
  onChoose,
  phone,
  profile,
}: {
  active: RequirementGroup;
  gapReasons: ReadonlyMap<string, string>;
  groups: readonly RequirementGroup[];
  onChoose: (importance: RequirementImportance) => void;
  phone: boolean;
  profile: string | null;
}) => {
  // oxlint-disable-next-line unicorn/no-array-sort
  const rows = [...active.requirements].sort(
    (left, right) => coverageOrder[left.coverage] - coverageOrder[right.coverage],
  );

  return (
    <div className="flex min-w-0 flex-col gap-3.5">
      {groups.length < 2 ? null : (
        <fieldset
          aria-label="סינון הדרישות"
          className="flex min-w-0 gap-2 max-lg:-mx-4 max-lg:overflow-x-auto max-lg:px-4 max-lg:py-0.5 lg:flex-wrap"
        >
          {groups.map((group) => (
            <FilterChip key={group.importance} onClick={() => onChoose(group.importance)} pressed={group === active}>
              {importanceLabels[group.importance]}
            </FilterChip>
          ))}
        </fieldset>
      )}

      {phone ? (
        <ul aria-label={importanceLabels[active.importance]} className={cardClasses("overflow-hidden")}>
          {rows.map((requirement) => (
            <PhoneRow
              gapReason={gapReasons.get(requirement.requirementId)}
              key={requirement.requirementId}
              profile={profile}
              requirement={requirement}
            />
          ))}
        </ul>
      ) : (
        <div className="overflow-x-auto rounded-surface border border-cv-hairline bg-cv-surface">
          <table className="w-full min-w-140 border-collapse text-label">
            <caption className="sr-only">{importanceLabels[active.importance]}</caption>
            <thead>
              <tr className="bg-cv-canvas text-start text-caption text-cv-text-muted">
                <th className="px-4.5 py-3 text-start font-bold" scope="col">
                  דרישה
                </th>
                <th className="px-4.5 py-3 text-start font-bold" scope="col">
                  כיסוי
                </th>
                <th className="px-4.5 py-3 text-start font-bold" scope="col">
                  פער
                </th>
                <th className="px-4.5 py-3 text-start font-bold" scope="col">
                  ראיות תומכות
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((requirement) => {
                const material = requirement.coverage !== "matched" && requirement.shortfallSeverity === "material";
                return (
                  <tr className="border-t border-cv-canvas" key={requirement.requirementId}>
                    <th className="px-4.5 py-3.5 text-start font-bold text-cv-text" scope="row">
                      <bdi>{requirement.text}</bdi>
                    </th>
                    <td className="px-4.5 py-3.5">
                      <CoverageBadge coverage={requirement.coverage} />
                    </td>
                    <td className={cx("px-4.5 py-3.5", material ? "font-bold text-cv-text" : "text-cv-text-muted")}>
                      {gapText(requirement)}
                    </td>
                    <td className="px-4.5 py-3.5 text-cv-text-muted">
                      {evidenceText(requirement) ?? factActionFor(requirement, profile)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
