import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, ShieldCheck } from "lucide-react";

import type { ReconciliationReport } from "@/api/contracts";
import { factsQueryPrefix } from "@/api/facts";
import { reconcile } from "@/api/maintenance";
import { Button } from "@/ui/Button";
import { cx } from "@/ui/cx";
import { Disclosure } from "@/ui/Disclosure";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { surfaceClasses } from "@/ui/surface";

/* The fact store checked against its lifecycle journal, and the stored artifacts against
   the database. It reports; it never writes. It sits on the facts screen because the
   reader who meets an out-of-sync fact needs the verdict here - and it stays one line:
   the answer is pass or fail, and only a failure has earned the room to explain itself. */

const verdictText = (report: ReconciliationReport): string => {
  const lifecycle = report.fact_lifecycle;
  if (report.passed) {
    const factCount = Object.values(lifecycle.fact_counts).reduce((total, count) => total + count, 0);
    return `תקין — ${factCount} עובדות, ${report.artifact_versions_checked} גרסאות תוצר.`;
  }
  const found = [
    lifecycle.problems.length === 0 ? null : `${lifecycle.problems.length} אי־התאמות בעובדות`,
    report.problems.length === 0 ? null : `${report.problems.length} בעיות בתוצרים`,
  ].filter((part) => part !== null);
  return `${found.join(", ")} — הבדיקה מדווחת בלבד ואינה מתקנת נתונים.`;
};

export const FactsIntegrityCheck = () => {
  const queryClient = useQueryClient();
  const check = useMutation({
    mutationFn: reconcile,
    /* The report describes the store as it is now, so the pool beside it is refetched
       rather than left showing the comparison the page loaded with. */
    onSuccess: () => queryClient.invalidateQueries({ queryKey: factsQueryPrefix }),
  });
  const report = check.data;
  const problems = report === undefined ? [] : [...report.fact_lifecycle.problems, ...report.problems];
  const Icon = report === undefined ? ShieldCheck : report.passed ? CircleCheck : CircleAlert;

  return (
    <div className={surfaceClasses("bg-cv-surface px-3.5 py-2.5")}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <Icon
          aria-hidden="true"
          className={cx(
            "size-icon-md shrink-0",
            report === undefined ? "text-cv-text-muted" : report.passed ? "text-cv-success" : "text-cv-blocker",
          )}
        />
        <span className="text-support font-semibold text-cv-text">בדיקת תקינות</span>
        {/* The verdict replaces the idle description rather than joining it: before a run
            there is nothing to report, and after one the result is the only thing worth
            the line. `<output>` announces it without stamping a role attribute. */}
        <output className="min-w-0 flex-1 text-support text-cv-text-muted">
          {report === undefined ? "העובדות מול יומן השינויים, והתוצרים מול מסד הנתונים." : verdictText(report)}
        </output>
        <Button
          onClick={() => check.mutate()}
          pending={check.isPending}
          pendingLabel="בודק…"
          size="compact"
          type="button"
          variant="secondary"
        >
          {report === undefined ? "הפעלה" : "בדיקה מחדש"}
        </Button>
      </div>
      {problems.length === 0 ? null : (
        <Disclosure className="mt-2" summary={`הבעיות שנמצאו (${problems.length})`}>
          <ul className="list-disc space-y-1 ps-5" dir="auto">
            {problems.map((problem) => (
              <li className="break-all font-mono text-caption text-cv-text" key={problem}>
                {problem}
              </li>
            ))}
          </ul>
        </Disclosure>
      )}
      {check.error === null ? null : (
        <ErrorCallout
          className="mt-2"
          error={check.error}
          fallbackDetail="לא ניתן היה להשלים את בדיקת התקינות."
          fallbackTitle="בדיקת התקינות נכשלה"
        />
      )}
    </div>
  );
};
