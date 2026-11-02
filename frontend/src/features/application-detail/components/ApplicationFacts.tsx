import type { ApplicationDetail } from "@/api/contracts";
import { fitLevelLabel } from "@/features/preparation";
import { surfaceClasses } from "@/ui/surface";
import { formatDateTime } from "@/utils/formatDateTime";
import { isApplicationClosed, lastSubmittedAt } from "../model/applicationHub";

/* The fit the analysis found, in words; an application not analysed yet says so rather
   than showing an empty value. */
export const fitText = (fitLevel: string | null | undefined): string =>
  fitLevel == null ? "טרם נותחה" : fitLevelLabel(fitLevel);

/* Three facts about the application a wide screen keeps beside its cards: how well it
   fits, whether it is still open, and when it was sent. A phone reads the same facts in
   the details sheet. */
export const ApplicationFacts = ({ detail }: { detail: ApplicationDetail }) => {
  const submitted = lastSubmittedAt(detail);
  const facts = [
    { term: "ציון התאמה", value: fitText(detail.application.fit_level) },
    { term: "סטטוס משרה", value: isApplicationClosed(detail) ? "סגורה" : "פתוחה" },
    { term: "הוגשה", value: submitted === null ? "טרם הוגשה" : formatDateTime(submitted, "date") },
  ];

  return (
    <dl className={surfaceClasses("m-0 divide-y divide-cv-canvas overflow-hidden bg-cv-surface")}>
      {facts.map((fact) => (
        <div className="flex items-center justify-between gap-3 px-4 py-3 text-support" key={fact.term}>
          <dt className="text-cv-text-muted">{fact.term}</dt>
          <dd className="m-0 font-bold text-cv-text">{fact.value}</dd>
        </div>
      ))}
    </dl>
  );
};
