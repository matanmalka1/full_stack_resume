import { useMemo, useState } from "react";

import type { AnalysisGap, Requirement, RequirementImportance } from "@/api/analyses";
import type { ApplicationDetail } from "@/api/contracts";
import { Callout } from "@/ui/Callout";
import { EmptyState } from "@/ui/EmptyState";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { ViewSwitch } from "@/ui/ViewSwitch";
import { type RequirementFilter, needsAttention, requirementGroups } from "../../model/requirementGroups";
import { RequirementRow } from "./RequirementRow";
import { useRequirementEvidence } from "./useRequirementEvidence";

const importanceTitles: Record<RequirementImportance, string> = {
  mandatory: "דרישות חובה",
  preferred: "דרישות מועדפות",
  unknown: "דרישות ללא חשיבות מוצהרת",
};

export const RequirementList = ({
  detail,
  gaps,
  requirements,
}: {
  detail: ApplicationDetail;
  gaps: AnalysisGap[];
  requirements: Requirement[];
}) => {
  const attentionCount = requirements.filter(needsAttention).length;
  const [filter, setFilter] = useState<RequirementFilter>(attentionCount > 0 ? "attention" : "all");
  const evidence = useRequirementEvidence(detail, requirements);
  const gapReasons = useMemo(() => new Map(gaps.map((gap) => [gap.requirementId, gap.reason])), [gaps]);
  const groups = requirementGroups(requirements, filter);
  const visible = groups.reduce((sum, group) => sum + group.requirements.length, 0);

  return (
    <section aria-labelledby="requirements-heading" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-body font-semibold text-cv-text" id="requirements-heading">
            דרישות המשרה
          </h3>
          <p className="text-support text-cv-text-muted">מה המשרה דורשת, ואילו עובדות מאושרות עונות על כל דרישה.</p>
        </div>
        <div className="max-w-full overflow-x-auto">
          <ViewSwitch
            label="סינון הדרישות"
            onChange={setFilter}
            options={[
              { label: `דורשות תשומת לב (${attentionCount})`, value: "attention" },
              { label: `מכוסות (${requirements.length - attentionCount})`, value: "matched" },
              { label: `הכל (${requirements.length})`, value: "all" },
            ]}
            value={filter}
          />
        </div>
      </div>

      {evidence.error == null ? null : (
        <ErrorCallout
          error={evidence.error}
          fallbackDetail="הדרישות עדיין מוצגות, אך לא ניתן להציג כרגע את נוסח העובדות התומכות."
          fallbackTitle="לא ניתן לטעון את הראיות התומכות"
        />
      )}
      {evidence.loading ? (
        // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
        <Callout role="status" title="טוען את הראיות התומכות…" tone="progress" />
      ) : null}

      {visible === 0 ? (
        <EmptyState>
          <p className="text-support text-cv-text-muted">
            {filter === "attention" ? "כל הדרישות מכוסות במלואן." : "אין דרישות להצגה במסנן הזה."}
          </p>
        </EmptyState>
      ) : (
        groups.map((group) =>
          group.requirements.length === 0 ? null : (
            <section aria-labelledby={`requirements-${group.importance}`} key={group.importance}>
              <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-cv-border pb-2">
                <h4 className="text-support font-bold text-cv-text" id={`requirements-${group.importance}`}>
                  {importanceTitles[group.importance]}
                </h4>
                <span className="text-caption font-semibold text-cv-text-muted">
                  {group.matched} מתוך {group.total} מכוסות במלואן
                </span>
              </div>
              <ul aria-labelledby={`requirements-${group.importance}`} className="divide-y divide-cv-border">
                {group.requirements.map((requirement) => (
                  <RequirementRow
                    evidence={evidence}
                    gapReason={gapReasons.get(requirement.requirementId)}
                    key={requirement.requirementId}
                    requirement={requirement}
                  />
                ))}
              </ul>
            </section>
          ),
        )
      )}
    </section>
  );
};
