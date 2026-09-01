import type { Classification } from "../../../api/analyses";
import { classificationItems, overrideKeyLabels } from "../analysisLabels";

/* The four classification axes - track, profile, emphasis, language - as a grid of small
   cards rather than a label/value list. They are what the draft will be built from and
   are read together as one verdict, not compared one row at a time, so each axis gets
   equal visual weight instead of being stacked in a column of pairs. */
export const ClassificationSummary = ({ classification }: { classification: Classification }) => {
  const decided = classification.decided
    .map((key) => overrideKeyLabels[key])
    .filter((label): label is string => label !== undefined);

  return (
    <div>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {classificationItems(classification).map((item, index) => (
          <div className="rounded-control border border-cv-border bg-cv-surface-muted p-3" key={index}>
            <dt className="text-support text-cv-text-muted">{item.term}</dt>
            <dd className="mt-1 text-body font-medium text-cv-text" dir="auto">
              {item.value}
            </dd>
          </div>
        ))}
      </dl>

      {decided.length === 0 ? null : (
        <p className="mt-3 text-support text-cv-text-muted" dir="auto">
          נקבע בהחלטה שלך: {decided.join(" · ")}.
        </p>
      )}
    </div>
  );
};
