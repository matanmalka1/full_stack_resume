import { useQuery } from "@tanstack/react-query";
import { Check, CircleAlert, FileCheck2, ShieldAlert } from "lucide-react";
import { useMemo } from "react";

import type {
  Requirement,
  RequirementCoverage,
  RequirementImportance,
  ShortfallSeverity,
} from "@/api/analyses";
import { factsQueryOptions } from "@/api/facts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Callout } from "@/ui/Callout";
import { StatusBadge } from "@/ui/StatusBadge";
import { cx } from "@/ui/cx";
import { coverageLabels, coverageTones } from "../../model/analysisLabels";
import { AnalysisSection } from "./AnalysisSection";

/* A posting that never says whether something is required is not thereby saying it is
   optional, so `unknown` is worded as exactly that rather than folded into "preferred". */
const importanceLabels: Record<RequirementImportance, string> = {
  mandatory: "דרישת חובה",
  preferred: "דרישה מועדפת",
  unknown: "חשיבות לא צוינה",
};

const shortfallLabels: Record<ShortfallSeverity, string> = {
  none: "אין פער",
  minor: "פער קטן",
  material: "פער מהותי",
  unknown: "חומרת הפער לא הוכרעה",
};

/* `unknown` sits between `partial` and `matched`: it is not evidence of a
   shortfall the way `unsupported`/`partial` are, but it is also not a settled
   `matched`, so a reader still sees it before the requirements that are actually
   covered. */
const coveragePriority: Record<RequirementCoverage, number> = {
  unsupported: 0,
  partial: 1,
  unknown: 2,
  matched: 3,
};

const orderedRequirements = (requirements: Requirement[]): Requirement[] =>
  // The spread already protects the input from mutation; ES2022 does not expose toSorted.
  // oxlint-disable-next-line unicorn/no-array-sort
  [...requirements].sort(
    (left, right) =>
      Number(right.importance === "mandatory") - Number(left.importance === "mandatory") ||
      coveragePriority[left.coverage] - coveragePriority[right.coverage],
  );

export const RequirementCoverageSummary = ({
  requirements,
  unreadableRequirementCount,
  hardGapCount,
}: {
  requirements: Requirement[];
  unreadableRequirementCount: number;
  hardGapCount: number;
}) => {
  const counts = requirements.reduce(
    (result, requirement) => {
      result[requirement.coverage] += 1;
      return result;
    },
    { matched: 0, partial: 0, unsupported: 0, unknown: 0 } satisfies Record<RequirementCoverage, number>,
  );
  const uncoveredMandatory = requirements.filter(
    (requirement) => requirement.importance === "mandatory" && requirement.coverage !== "matched",
  ).length;
  const metrics = [
    { label: "מכוסות", value: counts.matched },
    { label: "חלקיות", value: counts.partial },
    { label: "לא מכוסות", value: counts.unsupported },
    { label: "לא הוכרעו", value: counts.unknown },
  ];
  const total = requirements.length + unreadableRequirementCount;

  return (
    <AnalysisSection title="תמונת הכיסוי">
      <div className="flex flex-wrap items-end justify-between gap-4 border-y border-cv-border py-3">
        <div>
          <p className="text-heading-md font-bold text-cv-text">
            {counts.matched} מתוך {total}
          </p>
          <p className="text-support text-cv-text-muted">דרישות מכוסות במלואן</p>
        </div>
        <dl className="flex flex-wrap gap-x-5 gap-y-2">
          {metrics.map((metric) => (
            <div className="flex items-baseline gap-1.5" key={metric.label}>
              <dt className="text-support text-cv-text-muted">{metric.label}</dt>
              <dd className="text-body font-bold text-cv-text">{metric.value}</dd>
            </div>
          ))}
        </dl>
      </div>
      <Callout
        className="mt-3"
        title={
          hardGapCount === 0 && uncoveredMandatory === 0
            ? "אין דרישות חובה ללא כיסוי מלא."
            : hardGapCount === 0
              ? `${uncoveredMandatory} דרישות חובה דורשות תשומת לב, ללא פער קשיח.`
              : hardGapCount === 1
                ? "נמצא פער קשיח אחד בדרישות החובה."
                : `נמצאו ${hardGapCount} פערים קשיחים בדרישות החובה.`
        }
        tone={hardGapCount > 0 ? "blocker" : uncoveredMandatory > 0 ? "warning" : "success"}
      />
      {unreadableRequirementCount === 0 ? null : (
        <p className="mt-2 text-support text-cv-text-muted">לא ניתנות להצגה: {unreadableRequirementCount}</p>
      )}
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
  const ordered = orderedRequirements(requirements);
  const attentionRequirements = ordered.filter((requirement) => requirement.coverage !== "matched");
  const matchedRequirements = ordered.filter((requirement) => requirement.coverage === "matched");

  const requirementRow = (requirement: Requirement) => (
    <li className="py-4 first:pt-0 last:pb-0" key={requirement.requirementId}>
      <div className="flex items-start gap-3">
        <div
          className={cx(
            "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-pill border",
            requirement.coverage === "matched"
              ? "border-cv-success/30 bg-cv-success-soft text-cv-success"
              : "border-cv-warning/30 bg-cv-warning-soft text-cv-warning",
          )}
        >
          {requirement.coverage === "matched" ? (
            <Check aria-hidden="true" className="size-icon-md" />
          ) : (
            <CircleAlert aria-hidden="true" className="size-icon-md" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-body font-bold text-cv-text" dir="auto">
              {requirement.text}
            </h4>
            <StatusBadge tone={coverageTones[requirement.coverage]}>{coverageLabels[requirement.coverage]}</StatusBadge>
          </div>
          <p className="mt-0.5 text-caption font-semibold text-cv-text-muted">
            {importanceLabels[requirement.importance]}
          </p>
          {requirement.coverage === "matched" ? null : (
            <p className="mt-1 text-support text-cv-text-muted" dir="auto">
              <span className="font-bold text-cv-text">
                {shortfallLabels[requirement.shortfallSeverity ?? "unknown"]}:
                {" "}
              </span>
              {requirement.shortfallReason ?? "לא סופק הסבר מפורט לפער."}
            </p>
          )}

          {factsQuery.data === undefined ||
          (requirement.supportingFactIds.length === 0 && requirement.boundaryFactIds.length === 0) ? null : (
            <div className="mt-3 flex flex-col gap-2 border-s-2 border-cv-border ps-3">
              {requirement.supportingFactIds.length === 0 ? null : (
                <div className="flex items-start gap-2">
                  <FileCheck2 aria-hidden="true" className="mt-0.5 size-icon-sm shrink-0 text-cv-success" />
                  <p className="text-support text-cv-text-muted" dir="auto">
                    <span className="font-bold text-cv-text">ראיות תומכות: </span>
                    {requirement.supportingFactIds.map(factLabel).join(" · ")}
                  </p>
                </div>
              )}
              {requirement.boundaryFactIds.length === 0 ? null : (
                <div className="flex items-start gap-2">
                  <ShieldAlert aria-hidden="true" className="mt-0.5 size-icon-sm shrink-0 text-cv-warning" />
                  <p className="text-support text-cv-text-muted" dir="auto">
                    <span className="font-bold text-cv-text">למה הכיסוי מוגבל: </span>
                    {requirement.boundaryFactIds.map(factLabel).join(" · ")}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </li>
  );

  return (
    <AnalysisSection title="דרישות המשרה וכיסויין">
      <p className="mb-4 text-support text-cv-text-muted">
        הדרישות מסודרות לפי הצורך בפעולה. הראיות מוצגות בנוסחן הנוכחי במאגר.
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
        // role="status" is a Callout prop, not a DOM role; Callout already renders an
        // <output> for it.
        // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
        <Callout className="mb-3" role="status" title="טוען את הראיות התומכות…" tone="progress" />
      ) : factsQuery.error === null ? null : (
        <ErrorCallout
          className="mb-3"
          error={factsQuery.error}
          fallbackDetail="הדרישות עדיין מוצגות, אך לא ניתן להציג כרגע את נוסח העובדות התומכות."
          fallbackTitle="לא ניתן לטעון את הראיות התומכות"
        />
      )}
      <div aria-label="פירוט כיסוי דרישות המשרה">
        {attentionRequirements.length === 0 ? null : (
          <section aria-labelledby="requirements-attention-heading">
            <div className="flex items-center gap-2 border-b border-cv-border pb-2">
              <CircleAlert aria-hidden="true" className="size-icon-md text-cv-warning" />
              <h4 className="text-support font-bold text-cv-text" id="requirements-attention-heading">
                דורשות תשומת לב ({attentionRequirements.length})
              </h4>
            </div>
            <ul aria-labelledby="requirements-attention-heading" className="divide-y divide-cv-border">
              {attentionRequirements.map(requirementRow)}
            </ul>
          </section>
        )}

        {matchedRequirements.length === 0 ? null : (
          <section
            aria-labelledby="requirements-covered-heading"
            className={attentionRequirements.length === 0 ? undefined : "mt-6"}
          >
            <div className="flex items-center gap-2 border-b border-cv-border pb-2">
              <Check aria-hidden="true" className="size-icon-md text-cv-success" />
              <h4 className="text-support font-bold text-cv-text" id="requirements-covered-heading">
                מכוסות במלואן ({matchedRequirements.length})
              </h4>
            </div>
            <ul aria-labelledby="requirements-covered-heading" className="divide-y divide-cv-border">
              {matchedRequirements.map(requirementRow)}
            </ul>
          </section>
        )}
      </div>
    </AnalysisSection>
  );
};
