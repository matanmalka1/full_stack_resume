import type { Classification } from "@/api/analyses";
import { confidenceText } from "../../model/analysisLabels";

const Metric = ({ caption, label, value }: { caption?: string; label: string; value: string }) => (
  <div className="rounded-control bg-cv-surface-muted p-3">
    <p className="text-caption font-semibold text-cv-text-muted">{label}</p>
    <p className="mt-0.5 text-heading-sm font-bold text-cv-text">{value}</p>
    {caption === undefined ? null : <p className="mt-0.5 text-caption text-cv-text-muted">{caption}</p>}
  </div>
);

/* Coverage is stated once, here, split by importance. The hard-gap count belongs to the
   step banner, which explains how it caps the Fit level; the per-state breakdown is the
   requirement filter's own labels. */
export const AnalysisOverview = ({ classification }: { classification: Classification }) => {
  const { requirements } = classification;
  if (requirements.length === 0) {
    return null;
  }
  const mandatory = requirements.filter((requirement) => requirement.importance === "mandatory");
  const preferred = requirements.filter((requirement) => requirement.importance !== "mandatory");
  const covered = (items: typeof requirements) => items.filter((item) => item.coverage === "matched").length;

  return (
    <section aria-label="סיכום הכיסוי" className="grid gap-3 sm:grid-cols-3">
      <Metric
        caption={mandatory.length === 0 ? "המשרה לא הגדירה דרישות חובה" : undefined}
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
    </section>
  );
};
