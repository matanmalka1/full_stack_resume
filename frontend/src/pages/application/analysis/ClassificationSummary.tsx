import type { Classification } from "../../../api/analyses";
import { classificationItems, overrideKeyLabels } from "../analysisLabels";

/* The four classification axes, read as one flowing line rather than four boxed tiles:
   track, profile, emphasis, and language are one verdict - what the draft will be built
   from - not four separate metrics that each need a frame to stand apart. */
export const ClassificationSummary = ({ classification }: { classification: Classification }) => {
  const decided = classification.decided
    .map((key) => overrideKeyLabels[key])
    .filter((label): label is string => label !== undefined);

  return (
    <div>
      <p className="text-support leading-7" dir="auto">
        {classificationItems(classification).map((item, index) => (
          <span key={index}>
            {index === 0 ? null : <span className="text-cv-text-muted"> · </span>}
            <span className="text-cv-text-muted">{item.term}</span>{" "}
            <span className="font-medium text-cv-text">{item.value}</span>
          </span>
        ))}
      </p>

      {decided.length === 0 ? null : (
        <p className="mt-2 text-support text-cv-text-muted" dir="auto">
          נקבע בהחלטה שלך: {decided.join(" · ")}.
        </p>
      )}
    </div>
  );
};
