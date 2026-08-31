import type { ReactNode } from "react";

import type { Classification } from "../api/analyses";
import type { ApplicationDetail } from "../api/contracts";
import { Callout } from "../ui/Callout";
import { LtrText } from "../ui/LtrText";
import { StatusBadge } from "../ui/StatusBadge";
import { SummaryList } from "../ui/SummaryList";
import { TechnicalDetails } from "../ui/TechnicalDetails";
import {
  approvalReasonLabel,
  classificationItems,
  fitLabels,
  fitTones,
  gapSeverityLabels,
  overrideKeyLabels,
} from "./analysisLabels";

/* Confidence is a 0..1 float in the document and a percentage to a reader.

   The sign is the Hebrew-side one and the whole value is written into the sentence rather
   than wrapped in an A.3 LTR island. An island is for a Latin run that must not be
   reordered - an id, a code, a filename. A percentage is a number in a Hebrew sentence,
   and isolating it pushed the run to the end of the line, so "58%" arrived on screen
   reading "%58". */
const confidenceText = (confidence: number): string => `${Math.round(confidence * 100)}%`;

const Section = ({ children, title }: { children: ReactNode; title: string }) => (
  <div>
    <h3 className="mb-2 text-support font-semibold text-cv-text">{title}</h3>
    {children}
  </div>
);

/* A list of short backend-authored strings - keywords, requirements. Each picks its own
   direction: the analysis may be of an English posting while the shell is Hebrew, and a
   Hebrew-forced English requirement reads backwards. */
const TermList = ({ items }: { items: string[] }) => (
  <ul className="flex flex-wrap gap-2">
    {items.map((item) => (
      /* Output, not a control. The bordered pill is the shape the list filters use for
         things you can select, so these carry a flat tinted ground instead: same family,
         visibly not clickable. */
      <li
        className="rounded-control bg-cv-surface-muted px-2.5 py-1 text-support text-cv-text-muted"
        dir="auto"
        key={item}
      >
        {item}
      </li>
    ))}
  </ul>
);

/* What the analysis concluded, on the Application screen rather than behind a route of
   its own: the analysis is the reasoning behind the stage this screen already reports,
   and a separate screen would ask the reader to leave the actions to read it.

   It reports the analysis and offers nothing. Overriding a classification stays the
   review screen's, which the projection opens through `available_actions` - a second
   place to change the same values would be the second workflow state machine A.1
   forbids. */
export const AnalysisPanel = ({
  classification,
  detail,
}: {
  classification: Classification;
  detail: ApplicationDetail;
}) => {
  const analysis = detail.latest_analysis;
  /* A key this build does not recognise is dropped rather than printed: an internal
     token inside "you decided this" teaches the reader nothing. */
  const decided = classification.decided
    .map((key) => overrideKeyLabels[key])
    .filter((label): label is string => label !== undefined);

  return (
    <section aria-labelledby="analysis-heading" className="rounded-surface border border-cv-border p-5">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-cv-border pb-4">
        <h2 className="text-body font-semibold text-cv-text" id="analysis-heading">
          ניתוח המשרה
        </h2>
        {/* Confidence qualifies the fit, so it is read with it. Below the rationale it
            was muted support text under a paragraph, which put the number that says how
            far to trust the verdict further down the page than the verdict itself.

            The two are reported independently: a classification may carry a confidence
            without a fit, and hanging the number off the badge would have dropped it
            from the screen in exactly that case. */}
        {classification.fit === null && classification.confidence === null ? null : (
          <div className="flex flex-wrap items-center gap-2">
            {classification.fit === null ? null : (
              <StatusBadge tone={fitTones[classification.fit]}>
                {fitLabels[classification.fit]}
              </StatusBadge>
            )}
            {classification.confidence === null ? null : (
              <span className="text-support text-cv-text-muted">
                ברמת ביטחון {confidenceText(classification.confidence)}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-col gap-5">
        <SummaryList items={classificationItems(classification)} />

        {decided.length === 0 ? null : (
          <p className="text-support text-cv-text-muted" dir="auto">
            נקבע בהחלטה שלך: {decided.join(" · ")}.
          </p>
        )}

        {/* Why the classification is not settled. The projection's review reason says
            that a decision is needed and carries the action; this says what about the
            analysis made it necessary, which is the part a person needs in order to
            decide rather than merely to be told to. */}
        {classification.approvalReasons.length === 0 ? null : (
          <Section title="מה מחייב החלטה">
            <ul className="flex flex-col gap-1">
              {classification.approvalReasons.map((reason) => (
                <li className="text-support text-cv-text-muted" dir="auto" key={reason}>
                  {approvalReasonLabel(reason)}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {classification.rationale === null ? null : (
          <Section title="הנימוק">
            <p className="text-body leading-7 text-cv-text" dir="auto">
              {classification.rationale}
            </p>
          </Section>
        )}

        {classification.mandatoryRequirements.length === 0 ? null : (
          <Section title="דרישות חובה שזוהו">
            <TermList items={classification.mandatoryRequirements} />
          </Section>
        )}

        {classification.preferredRequirements.length === 0 ? null : (
          <Section title="דרישות מועדפות שזוהו">
            <TermList items={classification.preferredRequirements} />
          </Section>
        )}

        {classification.keywords.length === 0 ? null : (
          <Section title="מילות מפתח מהמשרה">
            <TermList items={classification.keywords} />
          </Section>
        )}

        {/* A gap is what the analysis could not match against the candidate facts. It is
            reported rather than resolved here: a hard gap is what blocks approval, and
            the projection's own review reason is what offers the decision. */}
        {classification.gaps.length === 0 ? null : (
          <Section title="פערים מול העובדות">
            <ul className="flex flex-col gap-3">
              {classification.gaps.map((gap) => (
                <li
                  className="rounded-surface border border-cv-border bg-cv-surface-muted p-3"
                  key={`${gap.severity}:${gap.requirement}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-support font-medium text-cv-text" dir="auto">
                      {gap.requirement}
                    </span>
                    <StatusBadge tone={gap.severity === "hard" ? "blocker" : "warning"}>
                      {gapSeverityLabels[gap.severity]}
                    </StatusBadge>
                  </div>
                  {gap.reason === "" ? null : (
                    <p className="mt-2 text-support text-cv-text-muted" dir="auto">
                      {gap.reason}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {analysis == null ? null : (
          <TechnicalDetails summary="מקור הניתוח ומזהיו">
            <SummaryList
              items={[
                { term: "מזהה הניתוח", value: analysis.id, ltr: true },
                { term: "גרסת הניתוח", value: String(analysis.version_number), ltr: true },
                { term: "תצלום המשרה", value: analysis.job_snapshot_id, ltr: true },
                { term: "ספק", value: analysis.provider, ltr: true },
                { term: "מודל", value: analysis.model, ltr: true },
                { term: "נוצר", value: analysis.created_at, ltr: true },
              ]}
            />
          </TechnicalDetails>
        )}
      </div>
    </section>
  );
};

/* A superseded analysis is not shown as if it were the one in force: the reader is told
   the analysis on record belongs to an older snapshot and that a new one is what the
   workflow is waiting on. The projection's stale and review reasons carry the action. */
export const SupersededAnalysisNote = () => (
  <Callout title="הניתוח שעל המסך אינו הניתוח הפעיל" tone="warning">
    הניתוח האחרון שנשמר נעשה מול תצלום משרה קודם, ולכן אינו מוצג כאן. ניתוח חדש מול
    התצלום הפעיל הוא מה שיציג את הסיווג העדכני.
  </Callout>
);
