import type { Classification } from "@/api/analyses";
import type { StatusTone } from "@/ui/status";
import { classificationItems, confidenceText, fitTones, overrideKeyLabels } from "../../model/analysisLabels";

/* The confidence figure's own text colour, one tone per fit level - reusing the same
   scale `StatusBadge` already draws the fit with, rather than a threshold invented for
   this one number. A classification with no fit at all (rather than an unreadable one,
   which `fitTones` already covers as "unknown") has no verdict to colour by, and reads in
   plain muted text instead. */
const confidenceToneClasses: Record<StatusTone, string> = {
  success: "text-cv-success",
  warning: "text-cv-warning",
  blocker: "text-cv-blocker",
  progress: "text-cv-accent",
  neutral: "text-cv-text-muted",
};

/* Track and profile are what the draft is actually built from, and confidence is how much
   to trust that pairing - the two headline figures this tab exists to show, so they lead
   as tiles rather than sitting in the same flowing line as emphasis and language. Emphasis
   and language still follow beneath them: nothing the analysis recorded is dropped, only
   reordered by how much weight each fact carries for the reader deciding whether to press
   on. */
export const ClassificationSummary = ({ classification }: { classification: Classification }) => {
  const decided = classification.decided
    .map((key) => overrideKeyLabels[key])
    .filter((label): label is string => label !== undefined);
  const [track, profile, ...extras] = classificationItems(classification);
  const trackProfileText = [track?.value, profile?.value].filter((value) => value !== undefined).join(" · ");
  const confidenceTone = classification.fit === null ? "neutral" : fitTones[classification.fit];

  return (
    <section>
      {trackProfileText === "" && classification.confidence === null ? null : (
        <div className="grid gap-3 sm:grid-cols-2">
          {trackProfileText === "" ? null : (
            <div className="rounded-control bg-cv-surface-muted p-3">
              <p className="text-support text-cv-text-muted">סיווג שהוצע</p>
              <p className="mt-0.5 text-body font-semibold text-cv-text" dir="auto">
                {trackProfileText}
              </p>
            </div>
          )}
          {classification.confidence === null ? null : (
            <div className="rounded-control bg-cv-surface-muted p-3">
              <p className="text-support text-cv-text-muted">רמת ביטחון</p>
              <p className={`mt-0.5 text-heading-sm font-bold ${confidenceToneClasses[confidenceTone]}`}>
                {confidenceText(classification.confidence)}
              </p>
            </div>
          )}
        </div>
      )}

      {extras.length === 0 ? null : (
        <p className="mt-3 text-support leading-7" dir="auto">
          {extras.map((item, index) => (
            <span key={index}>
              {index === 0 ? null : <span className="text-cv-text-muted"> · </span>}
              <span className="text-cv-text-muted">{item.term}</span>{" "}
              <span className="font-medium text-cv-text">{item.value}</span>
            </span>
          ))}
        </p>
      )}

      {decided.length === 0 ? null : (
        <p className="mt-2 text-support text-cv-text-muted" dir="auto">
          נקבע בהחלטה שלך: {decided.join(" · ")}.
        </p>
      )}
    </section>
  );
};
