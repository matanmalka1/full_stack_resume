import type { Classification, RequirementCoverage } from "@/api/analyses";
import { cx } from "@/ui/cx";
import { confidenceText, coverageLabels } from "../../model/analysisLabels";
import { coverageCounts } from "../../model/requirementGroups";

const segmentClasses: Record<RequirementCoverage, string> = {
  matched: "bg-cv-success",
  partial: "bg-cv-warning",
  unsupported: "bg-cv-blocker",
  unknown: "bg-cv-border-strong",
};

const segmentOrder: readonly RequirementCoverage[] = ["matched", "partial", "unsupported", "unknown"];

const Metric = ({ caption, label, value }: { caption?: string; label: string; value: string }) => (
  <div className="rounded-control bg-cv-surface-muted p-3">
    <p className="text-caption font-semibold text-cv-text-muted">{label}</p>
    <p className="mt-0.5 text-heading-sm font-bold text-cv-text">{value}</p>
    {caption === undefined ? null : <p className="mt-0.5 text-caption text-cv-text-muted">{caption}</p>}
  </div>
);

/* The analysis at a glance, without restating the verdict: the fit level and score are
   the step banner's, above this panel, and a second copy here is what made the two read
   as separate claims. What this adds is the split the banner cannot carry - how the
   mandatory and the preferred asks are covered, and how much of what was read is
   anchored in the posting's own text. */
export const AnalysisOverview = ({ classification }: { classification: Classification }) => {
  const { requirements } = classification;
  if (requirements.length === 0) {
    return null;
  }
  const mandatory = requirements.filter((requirement) => requirement.importance === "mandatory");
  const preferred = requirements.filter((requirement) => requirement.importance !== "mandatory");
  const covered = (items: typeof requirements) => items.filter((item) => item.coverage === "matched").length;
  const hardGaps = classification.gaps.filter((gap) => gap.severity === "hard").length;
  const counts = coverageCounts(requirements);

  return (
    <section aria-label="סיכום הכיסוי" className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <Metric
          caption={
            mandatory.length === 0
              ? "המשרה לא הגדירה דרישות חובה"
              : hardGaps === 0
                ? "ללא פער קשיח"
                : hardGaps === 1
                  ? "פער קשיח אחד"
                  : `${hardGaps} פערים קשיחים`
          }
          label="דרישות חובה מכוסות"
          value={mandatory.length === 0 ? "—" : `${covered(mandatory)}/${mandatory.length}`}
        />
        <Metric
          label="דרישות נוספות מכוסות"
          value={preferred.length === 0 ? "—" : `${covered(preferred)}/${preferred.length}`}
        />
        {classification.sourceCoverage === null ? null : (
          <Metric
            caption="מהדרישות אותרו בנוסח המודעה"
            label="עיגון במודעה"
            value={confidenceText(classification.sourceCoverage)}
          />
        )}
      </div>

      {/* The whole requirement set as one bar: the proportion a reader would otherwise
          have to add up from four separate numbers. The legend states every count in
          words, so the colours are never the only carrier (A.2). */}
      <div>
        <div aria-hidden="true" className="flex h-2 overflow-hidden rounded-pill bg-cv-surface-muted">
          {segmentOrder.map((coverage) =>
            counts[coverage] === 0 ? null : (
              <span
                className={segmentClasses[coverage]}
                key={coverage}
                style={{ width: `${(counts[coverage] / requirements.length) * 100}%` }}
              />
            ),
          )}
        </div>
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
          {segmentOrder.map((coverage) =>
            counts[coverage] === 0 ? null : (
              <li className="flex items-center gap-1.5 text-caption text-cv-text-muted" key={coverage}>
                <span aria-hidden="true" className={cx("size-2 rounded-pill", segmentClasses[coverage])} />
                {coverageLabels[coverage]}: <span className="font-semibold text-cv-text">{counts[coverage]}</span>
              </li>
            ),
          )}
        </ul>
      </div>
    </section>
  );
};
