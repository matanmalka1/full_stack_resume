import { Target } from "lucide-react";
import { useState } from "react";

import { type Classification, classificationFromAnalysis } from "@/api/analyses";
import type { RequirementImportance } from "@/api/analyses";
import { aiAvailability } from "@/api/settings";
import type { ApplicationDetail } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { cardClasses } from "@/ui/surface";
import { useAnalyzeCommand } from "../../api/mutations";
import { fitDescriptions, fitLabels } from "../../model/analysisLabels";
import { requirementGroups } from "../../model/requirementGroups";
import { AnalysisNotes } from "./AnalysisNotes";
import { GapQuestionsSection } from "./gaps/GapQuestionsSection";
import { RequirementsTable, limitText } from "./RequirementsTable";

/* The verdict, as the step's one dark block: the fit is what the reader opened the
   analysis for. A level is information, not an acknowledgement request - a low fit is
   shown and decided on by nobody, and the reader may still draft. */
const FitVerdict = ({ classification }: { classification: Classification }) => (
  <section
    aria-labelledby="fit-verdict-heading"
    className="flex flex-col gap-2 rounded-surface bg-cv-accent p-4.5 text-cv-on-accent shadow-floating max-lg:gap-1.5 max-lg:p-3.5"
  >
    <h2
      className="flex items-center gap-2 text-heading-sheet font-extrabold max-lg:text-heading-card"
      id="fit-verdict-heading"
    >
      <Target aria-hidden="true" className="size-5.5 shrink-0 lg:hidden" />
      {classification.fit === null ? "הניתוח הושלם" : fitLabels[classification.fit]}
    </h2>
    <p className="text-label leading-relaxed opacity-90">
      {classification.fit === null
        ? "הניתוח נשמר ללא דירוג התאמה. הדרישות למטה מראות מה כן נקרא מהמשרה."
        : fitDescriptions[classification.fit]}
    </p>
  </section>
);

/* Running the analysis again, beside the analysis it replaces. A paid call, said so
   beside the button rather than discovered after it. */
const Reanalyze = ({
  detail,
  onQueued,
  operationLive,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  operationLive: boolean;
}) => {
  const { analyze, settings } = useAnalyzeCommand(detail, onQueued);
  const ai = aiAvailability(settings);
  if (!detail.available_actions.includes("analyze")) return null;

  return (
    <div className="flex flex-col items-start gap-1">
      <Button
        disabled={operationLive || ai !== "available"}
        onClick={() => analyze.mutate()}
        pending={analyze.isPending}
        pendingLabel="מפעיל ניתוח…"
        variant="ghost"
        className="-ms-3.5"
      >
        ניתוח מחדש
      </Button>
      <p className="text-support leading-normal text-cv-text-muted">
        {ai === "missing" ? "ניתוח מחדש דורש ספק AI, ועדיין לא הוגדר כזה." : "ניתוח מחדש זה יכלול קריאת AI בתשלום."}
      </p>
    </div>
  );
};

/* The analysis step's body once there is an analysis: the verdict, the requirements it
   was read from by importance, why coverage stops where it does, and the questions about
   the requirements nothing covers (§9.1).

   A wide screen puts the requirements table, and the gap questions under it, beside a
   column holding the verdict and the explanations for the rows on view; a phone stacks
   the verdict over the rows, each folding its own explanation, then the questions. */
export const AnalysisOverview = ({
  detail,
  onQueued,
  operationLive,
  phone,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  operationLive: boolean;
  phone: boolean;
}) => {
  const classification = classificationFromAnalysis(detail);
  const [chosen, setChosen] = useState<RequirementImportance | null>(null);
  if (classification === null) return null;

  const groups = requirementGroups(classification.requirements);
  const active = groups.find((group) => group.importance === chosen) ?? groups[0];
  const gapReasons = new Map(classification.gaps.map((gap) => [gap.requirementId, gap.reason]));
  const limits =
    active === undefined
      ? []
      : active.requirements.flatMap((requirement) => {
          const text = limitText(requirement, gapReasons.get(requirement.requirementId));
          return text === null ? [] : [{ id: requirement.requirementId, requirement: requirement.text, text }];
        });

  const table =
    active === undefined ? (
      <p className={cardClasses("p-4 text-label text-cv-text-muted")}>הניתוח לא חילץ דרישות מנוסח המשרה.</p>
    ) : (
      <RequirementsTable
        active={active}
        gapReasons={gapReasons}
        groups={groups}
        onChoose={setChosen}
        phone={phone}
        profile={detail.application.profile ?? null}
      />
    );
  const gapQuestions = <GapQuestionsSection detail={detail} profile={classification.profile} />;
  const notes = (
    <AnalysisNotes
      issues={classification.issues}
      sourceCoverage={classification.sourceCoverage}
      unreadableRequirementCount={classification.unreadableRequirementCount}
    />
  );

  if (phone) {
    return (
      <div className="flex flex-col gap-3.5">
        <FitVerdict classification={classification} />
        {table}
        {gapQuestions}
        {notes}
        <Reanalyze detail={detail} onQueued={onQueued} operationLive={operationLive} />
      </div>
    );
  }

  return (
    <div className="flex items-start gap-5">
      <div className="flex min-w-0 flex-1 flex-col gap-5">
        {table}
        {gapQuestions}
      </div>
      <aside className="flex w-75 shrink-0 flex-col gap-3.5" aria-label="סיכום הניתוח">
        <FitVerdict classification={classification} />
        {limits.length === 0 ? null : (
          <section aria-labelledby="coverage-limits-heading" className={cardClasses("flex flex-col gap-2 p-4")}>
            <h2 className="text-label font-extrabold text-cv-text" id="coverage-limits-heading">
              מה מגביל את הכיסוי
            </h2>
            <ul className="flex flex-col gap-2.5">
              {limits.map((limit) => (
                <li className="text-label leading-relaxed text-cv-text-muted" key={limit.id}>
                  {limits.length === 1 ? null : <bdi className="block font-bold text-cv-text">{limit.requirement}</bdi>}
                  <bdi>{limit.text}</bdi>
                </li>
              ))}
            </ul>
          </section>
        )}
        {notes}
        <Reanalyze detail={detail} onQueued={onQueued} operationLive={operationLive} />
      </aside>
    </div>
  );
};
