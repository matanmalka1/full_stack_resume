import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import type { Requirement, RequirementCoverage } from "../../../api/analyses";
import { factsQueryOptions } from "../../../api/facts";
import { StatusBadge } from "../../../ui/StatusBadge";
import { cx } from "../../../ui/cx";
import { coverageLabels, coverageTones } from "../analysisLabels";
import { AnalysisSection } from "./AnalysisSection";

const coverageBorderClasses: Record<RequirementCoverage, string> = {
  matched: "border-cv-success/50",
  partial: "border-cv-warning/50",
  unsupported: "border-cv-blocker/50",
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
export const RequirementCoverageSection = ({ requirements }: { requirements: Requirement[] }) => {
  const factsQuery = useQuery(factsQueryOptions());
  const factMeanings = useMemo(() => {
    const meanings = new Map<string, string>();
    for (const item of factsQuery.data?.items ?? []) {
      meanings.set(item.fact.fact_id, item.fact.meaning);
    }
    return meanings;
  }, [factsQuery.data]);

  if (requirements.length === 0) {
    return null;
  }

  const factLabel = (factId: string): string => factMeanings.get(factId) ?? "לא ניתן לקרוא את העובדה הזו מהידע.";

  return (
    <AnalysisSection title="דרישות המשרה וכיסויין">
      <ul className="flex flex-col gap-3">
        {requirements.map((requirement) => (
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

            {requirement.supportingFactIds.length === 0 ? null : (
              <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                עובדות תומכות: {requirement.supportingFactIds.map(factLabel).join(" · ")}
              </p>
            )}

            {/* Named separately from support on purpose: a boundary fact caps coverage
                rather than adding to it, and listing it beside "עובדות תומכות" would read
                as more evidence for a requirement the analysis just said falls short. */}
            {requirement.boundaryFactIds.length === 0 ? null : (
              <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                עובדות גובלות (אינן נחשבות כעדות תומכת): {requirement.boundaryFactIds.map(factLabel).join(" · ")}
              </p>
            )}

            {requirement.missingComponents.length === 0 ? null : (
              <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                מה חסר:{" "}
                {requirement.missingComponents
                  .map((component) => (component.demanded === null ? component.label : `${component.label} (נדרש: ${component.demanded})`))
                  .join(" · ")}
              </p>
            )}
          </li>
        ))}
      </ul>
    </AnalysisSection>
  );
};
