import { Code2, Lock, ShieldCheck } from "lucide-react";

import type { ApprovedRevision } from "../../api/contracts";
import { approvedPreviewSrc, type DecisionMarkdownDownload } from "../../api/revisions";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Card } from "../../ui/Card";
import { SummaryList } from "../../ui/SummaryList";
import { surfaceClasses } from "../../ui/Surface";
import { ValidationReportView } from "./ValidationReportView";

interface RevisionRecordProps {
  decision: DecisionMarkdownDownload | undefined;
  onDownloadDecision: () => void;
  revision: ApprovedRevision;
}

export const RevisionRecord = ({ decision, onDownloadDecision, revision }: RevisionRecordProps) => (
  <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(19rem,1fr)]">
    {/* The server-rendered document is the authoritative presentation. No candidate
        wording or artifact metadata is reconstructed in React. */}
    <div className="min-w-0">
      {revision.html_artifact_version_id == null ? (
        <Callout title="עדיין אין קובץ HTML לתצוגה" tone="neutral">
          הגרסה המאושרת נשמרה, אך תצוגת המסמך תופיע רק לאחר יצירת הארטיפקט הרשום.
        </Callout>
      ) : (
        <iframe
          className={surfaceClasses("h-[46rem] w-full bg-cv-surface-raised shadow-document")}
          sandbox=""
          src={approvedPreviewSrc(revision.id, revision.html_artifact_version_id)}
          title="תצוגה מאושרת של קורות החיים"
        />
      )}
    </div>

    <aside aria-label="פרטי הגרסה והאימות" className="flex min-w-0 flex-col gap-6">
      <Card aria-labelledby="revision-record-heading" className="overflow-x-auto bg-cv-surface p-4 shadow-surface">
        <h2 className="flex items-center gap-2 font-semibold text-cv-text" id="revision-record-heading">
          <Lock aria-hidden="true" className="size-4 text-cv-accent" />
          הרשומה הקבועה
        </h2>
        <SummaryList
          className="mt-4"
          items={[
            { term: "מזהה גרסה", value: revision.id, ltr: true },
            { term: "מספר גרסה", value: revision.version_number, ltr: true },
            { term: "תצלום משרה", value: revision.job_snapshot_id, ltr: true },
            { term: "ריצת אימות", value: revision.validation_run_id, ltr: true },
            { term: "חתימת הטיוטה", value: revision.draft_content_hash, ltr: true },
            { term: "קובץ HTML", value: revision.html_artifact_version_id == null ? "חסר" : "קיים" },
            { term: "קובץ PDF", value: revision.pdf_artifact_version_id == null ? "חסר" : "קיים" },
          ]}
        />
      </Card>

      <Card aria-labelledby="ready-validation-heading" className="bg-cv-surface p-4 shadow-surface">
        <h2 className="mb-4 flex items-center gap-2 font-semibold text-cv-text" id="ready-validation-heading">
          <ShieldCheck aria-hidden="true" className="size-4 text-cv-accent" />
          אימות הגרסה המוכנה
        </h2>
        <ValidationReportView report={revision.ready_validation} />
      </Card>

      {decision === undefined ? null : (
        <details className={surfaceClasses("bg-cv-surface-muted p-4")}>
          <summary className="cursor-pointer font-semibold text-cv-text">הסבר ההחלטות של הגרסה</summary>
          <p className="mt-2 text-support text-cv-text-muted">
            מסמך קריא שמסביר מה נבחר, אילו פערים התקבלו ואילו חריגות נרשמו.
          </p>
          <pre
            className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap rounded-control border border-cv-border bg-cv-surface p-4 text-support"
            dir="auto"
          >
            {decision.content}
          </pre>
          <Button className="mt-3" onClick={onDownloadDecision} variant="secondary">
            <Code2 aria-hidden="true" className="size-4" />
            הורדת מסמך ההחלטה
          </Button>
        </details>
      )}
    </aside>
  </div>
);
