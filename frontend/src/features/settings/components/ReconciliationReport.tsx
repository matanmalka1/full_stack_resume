import type { ReconciliationReport as ReconciliationReportData } from "@/api/contracts";
import { Callout } from "@/ui/Callout";
import { LtrText } from "@/ui/LtrText";
import { surfaceClasses } from "@/ui/surface";
import { type SummaryItem, SummaryList } from "@/ui/SummaryList";

const MISSING_ARTIFACT_PREFIX = "missing artifact:";

const lifecycleSummaryItems = (lifecycle: ReconciliationReportData["fact_lifecycle"]): SummaryItem[] => [
  { term: "עובדות במעקב ביומן", value: lifecycle.tracked_facts },
  { term: "רשומות יומן בהכנה", value: lifecycle.journal_prepared },
  { term: "רשומות יומן בהסגר", value: lifecycle.journal_quarantined },
  {
    term: "גרסת מקור העובדות",
    value: (
      <LtrText className="break-all" mono>
        {lifecycle.facts_version}
      </LtrText>
    ),
  },
  {
    term: "גרסת מחזור החיים",
    value: (
      <LtrText className="break-all" mono>
        {lifecycle.lifecycle_version}
      </LtrText>
    ),
  },
];

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

export const ReconciliationReport = ({ report }: { report: ReconciliationReportData }) => {
  const lifecycle = report.fact_lifecycle;
  const factCounts = Object.entries(lifecycle.fact_counts).sort(([left], [right]) => left.localeCompare(right));
  const factCount = factCounts.reduce((total, [, count]) => total + count, 0);
  const missingArtifacts = report.problems.filter((problem) => problem.startsWith(MISSING_ARTIFACT_PREFIX));
  const otherArtifactProblems = report.problems.length - missingArtifacts.length;
  const artifactsPassed = report.problems.length === 0;

  return (
    <div aria-label="דוח בדיקת התאמה" className="flex w-full flex-col gap-5">
      <Callout
        role="status"
        title={report.passed ? "הנתונים והתוצרים תקינים" : "נמצאה בעיית תקינות"}
        tone={report.passed ? "success" : "blocker"}
      >
        {report.passed ? "לא נדרשת פעולה." : "הבדיקה מדווחת על הבעיה אך אינה משנה או מתקנת נתונים."}
      </Callout>

      <section aria-labelledby="result-summary-heading">
        <h3 className="text-support font-bold" id="result-summary-heading">
          מה נמצא
        </h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className={surfaceClasses("p-4")}>
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
          <div className={surfaceClasses("p-4")}>
            <p className="text-support font-bold">מאגר העובדות</p>
            <p className="mt-1 text-body font-semibold">{lifecycle.passed ? "תקין" : "נמצאה אי־התאמה"}</p>
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
          יש לבדוק שהמערכת מחוברת לתיקיית התוצרים או ל־bucket הנכונים. אם הקבצים נמחקו, יש לשחזר אותם מגיבוי. עד אז
          הגרסאות הקשורות אליהם עלולות לא להיות זמינות להורדה או לא להיחשב מוכנות.
        </Callout>
      )}

      {lifecycle.passed ? null : (
        <Callout title="נדרשת בדיקה של מאגר העובדות" tone="warning">
          יש לבדוק את קובצי העובדות ואת יומן השינויים לפני שממשיכים לעבוד עם עובדות תלויות. הבדיקה אינה משנה או מתקנת
          אותם.
        </Callout>
      )}

      <details className={surfaceClasses("p-4")}>
        <summary className="cursor-pointer text-support font-semibold text-cv-accent">פרטים טכניים</summary>
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
            <SummaryList className="mt-2 text-caption" items={lifecycleSummaryItems(lifecycle)} />
            <h5 className="mt-4 text-caption font-bold">ספירה לפי מצב</h5>
            <dl className="mt-2 grid gap-2 sm:grid-cols-2">
              {factCounts.map(([status, count]) => (
                <div className="flex justify-between gap-4 rounded-control bg-cv-surface-muted px-3 py-2" key={status}>
                  <dt className="text-caption" dir="auto">
                    {status}
                  </dt>
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
