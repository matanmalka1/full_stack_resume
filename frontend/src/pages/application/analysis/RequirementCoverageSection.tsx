import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import type { Requirement, RequirementCoverage } from "../../../api/analyses";
import { factsQueryOptions } from "../../../api/facts";
import { ErrorCallout } from "../../../app/ErrorCallout";
import { Callout } from "../../../ui/Callout";
import { StatusBadge } from "../../../ui/StatusBadge";
import { cx } from "../../../ui/cx";
import { coverageLabels, coverageTones } from "../analysisLabels";
import { AnalysisSection } from "./AnalysisSection";

const coverageBorderClasses: Record<RequirementCoverage, string> = {
  matched: "border-cv-success/50",
  partial: "border-cv-warning/50",
  unsupported: "border-cv-blocker/50",
};

const coveragePriority: Record<RequirementCoverage, number> = {
  unsupported: 0,
  partial: 1,
  matched: 2,
};

const orderedRequirements = (requirements: Requirement[]): Requirement[] =>
  [...requirements].sort(
    (left, right) =>
      Number(right.mandatory) - Number(left.mandatory) ||
      coveragePriority[left.coverage] - coveragePriority[right.coverage],
  );

export const RequirementCoverageSummary = ({
  requirements,
  unreadableRequirementCount,
}: {
  requirements: Requirement[];
  unreadableRequirementCount: number;
}) => {
  const counts = requirements.reduce(
    (result, requirement) => ({ ...result, [requirement.coverage]: result[requirement.coverage] + 1 }),
    { matched: 0, partial: 0, unsupported: 0 } satisfies Record<RequirementCoverage, number>,
  );
  const uncoveredMandatory = requirements.filter(
    (requirement) => requirement.mandatory && requirement.coverage !== "matched",
  ).length;

  return (
    <AnalysisSection title="תמונת הכיסוי">
      <div className="flex flex-wrap gap-2">
        <StatusBadge tone="success">מכוסות: {counts.matched}</StatusBadge>
        <StatusBadge tone="warning">חלקיות: {counts.partial}</StatusBadge>
        <StatusBadge tone="blocker">לא מכוסות: {counts.unsupported}</StatusBadge>
        {unreadableRequirementCount === 0 ? null : (
          <StatusBadge tone="warning">לא ניתנות להצגה: {unreadableRequirementCount}</StatusBadge>
        )}
      </div>
      <p className="mt-2 text-support text-cv-text-muted">
        {uncoveredMandatory === 0
          ? "אין דרישות חובה ללא כיסוי מלא."
          : uncoveredMandatory === 1
            ? "דרישת חובה אחת עדיין אינה מכוסה במלואה."
            : `${uncoveredMandatory} דרישות חובה עדיין אינן מכוסות במלואן.`}
      </p>
    </AnalysisSection>
  );
};

/* The full requirement picture, matched requirements included - what the mandatory and
   preferred term lists never showed. Those two lists, and the gaps section below them,
   are the same requirements' unmet projection; this section is where a reader sees a
   requirement is covered at all, and which canonical facts cover it.

   Fact ids arrive bare from the analysis document - it names evidence by id, not by the
   text an id currently resolves to, since a fact's wording can change after the analysis
   was written. This section reads current canonical text for that id from the facts
   list, the same defensively-narrow way the rest of this screen reads the analysis: an
   id nothing resolves is named as such rather than hidden. */
export const RequirementCoverageSection = ({
  requirements,
  unreadableRequirementCount,
}: {
  requirements: Requirement[];
  unreadableRequirementCount: number;
}) => {
  const hasEvidenceIds = requirements.some(
    (requirement) => requirement.supportingFactIds.length > 0 || requirement.boundaryFactIds.length > 0,
  );
  const factsQuery = useQuery({ ...factsQueryOptions(), enabled: hasEvidenceIds });
  const factMeanings = useMemo(() => {
    const meanings = new Map<string, string>();
    for (const item of factsQuery.data?.items ?? []) {
      meanings.set(item.fact.fact_id, item.fact.meaning);
    }
    return meanings;
  }, [factsQuery.data]);

  if (requirements.length === 0 && unreadableRequirementCount === 0) {
    return null;
  }

  const factLabel = (factId: string): string => factMeanings.get(factId) ?? `העובדה ${factId} אינה קיימת במאגר הנוכחי.`;

  return (
    <AnalysisSection title="דרישות המשרה וכיסויין">
      <p className="mb-3 text-support text-cv-text-muted">
        הראיות מוצגות בנוסחן הנוכחי במאגר. דרישות חובה ופערים מוצגים ראשונים.
      </p>
      {unreadableRequirementCount === 0 ? null : (
        <Callout
          className="mb-3"
          title={
            unreadableRequirementCount === 1
              ? "דרישה אחת אינה ניתנת להצגה"
              : `${unreadableRequirementCount} דרישות אינן ניתנות להצגה`
          }
          tone="warning"
        >
          הרשומות לא היו תקינות ולכן אינן נכללות בתמונת הכיסוי.
        </Callout>
      )}
      {factsQuery.isLoading ? (
        <Callout className="mb-3" role="status" title="טוען את הראיות התומכות…" tone="progress" />
      ) : factsQuery.error === null ? null : (
        <ErrorCallout
          className="mb-3"
          error={factsQuery.error}
          fallbackDetail="הדרישות עדיין מוצגות, אך לא ניתן להציג כרגע את נוסח העובדות התומכות."
          fallbackTitle="לא ניתן לטעון את הראיות התומכות"
        />
      )}
      <ul className="flex flex-col gap-3">
        {orderedRequirements(requirements).map((requirement) => (
          <li
            className={cx("border-s-2 ps-3", coverageBorderClasses[requirement.coverage])}
            key={requirement.requirementId}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-support font-medium text-cv-text" dir="auto">
                {requirement.text}
              </span>
              <StatusBadge tone={coverageTones[requirement.coverage]}>
                {coverageLabels[requirement.coverage]}
              </StatusBadge>
              <span className="text-support text-cv-text-muted">
                {requirement.mandatory ? "דרישת חובה" : "דרישה מועדפת"}
              </span>
            </div>

            {factsQuery.data === undefined || requirement.supportingFactIds.length === 0 ? null : (
              <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                ראיות תומכות (מהמאגר הנוכחי): {requirement.supportingFactIds.map(factLabel).join(" · ")}
              </p>
            )}

            {/* Named separately from support on purpose: a boundary fact caps coverage
                rather than adding to it, and listing it beside "עובדות תומכות" would read
                as more evidence for a requirement the analysis just said falls short. */}
            {factsQuery.data === undefined || requirement.boundaryFactIds.length === 0 ? null : (
              <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                למה הכיסוי מוגבל: {requirement.boundaryFactIds.map(factLabel).join(" · ")}
              </p>
            )}

            {requirement.missingComponents.length === 0 ? null : (
              <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                מה חסר:{" "}
                {requirement.missingComponents
                  .map((component) =>
                    component.demanded === null ? component.label : `${component.label} (נדרש: ${component.demanded})`,
                  )
                  .join(" · ")}
              </p>
            )}
          </li>
        ))}
      </ul>
    </AnalysisSection>
  );
};
