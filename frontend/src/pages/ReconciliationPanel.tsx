import { useMutation } from "@tanstack/react-query";

import type { ReconciliationReport } from "../api/contracts";
import { reconcile } from "../api/maintenance";
import { ErrorCallout } from "../app/ErrorCallout";
import { Button } from "../ui/Button";
import { Callout } from "../ui/Callout";

const MISSING_ARTIFACT_PREFIX = "missing artifact:";

const TechnicalProblems = ({ problems }: { problems: string[] }) =>
  problems.length === 0 ? (
    <p className="mt-2 text-support text-cv-text-muted">לא נרשמו בעיות.</p>
  ) : (
    <ul className="mt-2 list-disc space-y-2 ps-5 text-caption text-cv-text" dir="auto">
      {problems.map((problem, index) => (
        <li className="break-all font-mono" key={`${index}-${problem}`}>
          {problem}
        </li>
      ))}
    </ul>
  );

const Report = ({ report }: { report: ReconciliationReport }) => {
  const lifecycle = report.fact_lifecycle;
  const factCounts = Object.entries(lifecycle.fact_counts).sort(([left], [right]) =>
    left.localeCompare(right),
  );
  const factCount = factCounts.reduce((total, [, count]) => total + count, 0);
  const missingArtifacts = report.problems.filter((problem) =>
    problem.startsWith(MISSING_ARTIFACT_PREFIX),
  );
  const otherArtifactProblems = report.problems.length - missingArtifacts.length;
  const artifactsPassed = report.problems.length === 0;

  return (
    <div className="flex w-full flex-col gap-5" aria-label="דוח בדיקת התאמה">
      <Callout
        role="status"
        title={report.passed ? "הנתונים והתוצרים תקינים" : "נמצאה בעיית תקינות"}
        tone={report.passed ? "success" : "blocker"}
      >
        {report.passed
          ? "לא נדרשת פעולה."
          : "הבדיקה מדווחת על הבעיה אך אינה משנה או מתקנת נתונים."}
      </Callout>

      <section aria-labelledby="result-summary-heading">
        <h3 className="text-support font-bold" id="result-summary-heading">
          מה נמצא
        </h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="rounded-surface border border-cv-border p-4">
            <p className="text-support font-bold">תוצרים שמורים</p>
            <p className="mt-1 text-body font-semibold">
              {artifactsPassed
                ? "תקין"
                : missingArtifacts.length > 0
                  ? `קבצים חסרים: ${missingArtifacts.length}`
                  : `נמצאו בעיות: ${otherArtifactProblems}`}
            </p>
            <p className="mt-2 text-support text-cv-text-muted">
              {artifactsPassed
                ? `${report.artifact_versions_checked} גרסאות תוצר נמצאו באחסון.`
                : "מסד הנתונים מפנה לקבצי קורות חיים שאינם קיימים באחסון."}
            </p>
            {otherArtifactProblems === 0 ? null : (
              <p className="mt-2 text-support text-cv-blocker">
                בנוסף נמצאו {otherArtifactProblems} בעיות אחסון אחרות.
              </p>
            )}
          </div>
          <div className="rounded-surface border border-cv-border p-4">
            <p className="text-support font-bold">מאגר העובדות</p>
            <p className="mt-1 text-body font-semibold">
              {lifecycle.passed ? "תקין" : "נמצאה אי־התאמה"}
            </p>
            <p className="mt-2 text-support text-cv-text-muted">
              {lifecycle.passed
                ? `${factCount} עובדות במקור; הבדיקה מול יומן השינויים תקינה.`
                : "קובצי העובדות ויומן השינויים אינם תואמים."}
            </p>
          </div>
        </div>
      </section>

      {missingArtifacts.length === 0 ? null : (
        <Callout title="מה צריך לעשות" tone="warning">
          יש לבדוק שהמערכת מחוברת לתיקיית התוצרים או ל־bucket הנכונים. אם הקבצים
          נמחקו, יש לשחזר אותם מגיבוי. עד אז הגרסאות הקשורות אליהם עלולות לא להיות
          זמינות להורדה או לא להיחשב מוכנות.
        </Callout>
      )}

      {lifecycle.passed ? null : (
        <Callout title="נדרשת בדיקה של מאגר העובדות" tone="warning">
          יש לבדוק את קובצי העובדות ואת יומן השינויים לפני שממשיכים לעבוד עם עובדות
          תלויות. הבדיקה אינה משנה או מתקנת אותם.
        </Callout>
      )}

      <details className="rounded-surface border border-cv-border p-4">
        <summary className="cursor-pointer text-support font-semibold text-cv-accent">
          פרטים טכניים
        </summary>
        <div className="mt-4 space-y-5">
          <section aria-labelledby="artifact-technical-heading">
            <h4 className="text-support font-bold" id="artifact-technical-heading">
              תוצרים — {report.artifact_versions_checked} גרסאות נבדקו
            </h4>
            <TechnicalProblems problems={report.problems} />
          </section>

          <section aria-labelledby="fact-technical-heading">
            <h4 className="text-support font-bold" id="fact-technical-heading">
              מחזור חיי העובדות
            </h4>
            <dl className="mt-2 grid gap-3 text-caption sm:grid-cols-2">
              <div>
                <dt className="text-cv-text-muted">עובדות במעקב ביומן</dt>
                <dd className="font-semibold">{lifecycle.tracked_facts}</dd>
              </div>
              <div>
                <dt className="text-cv-text-muted">רשומות יומן בהכנה</dt>
                <dd className="font-semibold">{lifecycle.journal_prepared}</dd>
              </div>
              <div>
                <dt className="text-cv-text-muted">רשומות יומן בהסגר</dt>
                <dd className="font-semibold">{lifecycle.journal_quarantined}</dd>
              </div>
              <div>
                <dt className="text-cv-text-muted">גרסת מקור העובדות</dt>
                <dd className="break-all font-mono" dir="auto">{lifecycle.facts_version}</dd>
              </div>
              <div>
                <dt className="text-cv-text-muted">גרסת מחזור החיים</dt>
                <dd className="break-all font-mono" dir="auto">{lifecycle.lifecycle_version}</dd>
              </div>
            </dl>
            <h5 className="mt-4 text-caption font-bold">ספירה לפי מצב</h5>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
              {factCounts.map(([status, count]) => (
                <div
                  className="flex justify-between gap-4 rounded-control bg-cv-surface-muted px-3 py-2"
                  key={status}
                >
                  <dt className="text-caption" dir="auto">{status}</dt>
                  <dd className="text-caption font-semibold">{count}</dd>
                </div>
              ))}
            </dl>
            <TechnicalProblems problems={lifecycle.problems} />
          </section>
        </div>
      </details>
    </div>
  );
};

export const ReconciliationPanel = () => {
  const reconciliation = useMutation({ mutationFn: reconcile });

  return (
    <section aria-labelledby="reconciliation-heading" className="border-t border-cv-border pt-6">
      <h2 className="text-heading-sm font-bold" id="reconciliation-heading">
        תחזוקה
      </h2>
      <p className="mt-2 max-w-2xl text-support text-cv-text-muted">
        בדיקת התאמה בין מסד הנתונים, התוצרים השמורים ומחזור חיי העובדות. הבדיקה
        מדווחת בלבד ואינה מתקנת נתונים.
      </p>
      <div className="mt-4 flex flex-col items-start gap-6">
        <Button
          onClick={() => reconciliation.mutate()}
          pending={reconciliation.isPending}
          pendingLabel="בודק התאמה…"
          type="button"
        >
          הפעלת בדיקת התאמה
        </Button>
        {reconciliation.data === undefined ? null : <Report report={reconciliation.data} />}
        {reconciliation.error === null ? null : (
          <ErrorCallout
            error={reconciliation.error}
            fallbackDetail="לא ניתן היה להשלים את בדיקת ההתאמה."
            fallbackTitle="בדיקת ההתאמה נכשלה"
          />
        )}
      </div>
    </section>
  );
};
