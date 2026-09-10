import { Code2, Lock, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import type { ApprovedRevision } from "@/api/contracts";
import { approvedPreviewSrc, type DecisionMarkdownDownload } from "@/api/revisions";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { Disclosure } from "@/ui/Disclosure";
import { DocumentFrame } from "@/ui/DocumentFrame";
import { SummaryList } from "@/ui/SummaryList";
import { surfaceClasses } from "@/ui/surface";
import { ValidationReportView } from "./ValidationReportView";

interface RevisionRecordProps {
  additionalOptions?: ReactNode;
  decision: DecisionMarkdownDownload | undefined;
  revision: ApprovedRevision;
}

export const RevisionRecord = ({ additionalOptions, decision, revision }: RevisionRecordProps) => {
  const downloadDecision = () => {
    if (decision === undefined) return;
    const href = URL.createObjectURL(new Blob([decision.content], { type: "text/markdown;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = decision.filename;
    anchor.click();
    URL.revokeObjectURL(href);
  };

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(19rem,1fr)]">
      {/* The server-rendered document is the authoritative presentation. No candidate
        wording or artifact metadata is reconstructed in React. */}
      <div className="min-w-0">
        {revision.html_artifact_version_id == null ? (
          <Callout title="עדיין אין קובץ HTML לתצוגה" tone="neutral">
            הגרסה המאושרת נשמרה, אך תצוגת המסמך תופיע רק לאחר יצירת הארטיפקט הרשום.
          </Callout>
        ) : (
          <DocumentFrame
            className={surfaceClasses("w-full bg-cv-surface-raised shadow-document")}
            src={approvedPreviewSrc(revision.id, revision.html_artifact_version_id)}
            title="תצוגה מאושרת של קורות החיים"
          />
        )}
      </div>

      <aside aria-label="פרטי הגרסה והאימות" className="flex min-w-0 flex-col gap-6">
        <Disclosure summary="פרטים טכניים וביקורת">
          <Card aria-labelledby="revision-record-heading" className="overflow-x-auto bg-cv-surface p-4 shadow-surface">
            <h2 className="flex items-center gap-2 font-semibold text-cv-text" id="revision-record-heading">
              <Lock aria-hidden="true" className="size-icon-md text-cv-accent" />
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
        </Disclosure>

        <Card aria-labelledby="ready-validation-heading" className="bg-cv-surface p-4 shadow-surface">
          <h2 className="mb-4 flex items-center gap-2 font-semibold text-cv-text" id="ready-validation-heading">
            <ShieldCheck aria-hidden="true" className="size-icon-md text-cv-accent" />
            אימות הגרסה המוכנה
          </h2>
          <ValidationReportView report={revision.ready_validation} />
        </Card>

        {/* Secondary actions belong beside the record they affect. On the wide Ready
            layout this fills the space below validation instead of leaving the aside
            empty while the controls sit below the entire document grid; when the grid
            stacks, the same slot preserves their reading order after validation. */}
        {additionalOptions}

        {/* The third of three peers in this aside, and for a while the only one drawn by
            hand: a bare `<details>` on a filled panel, opened by the user agent's own
            triangle, beside a `Disclosure` and a `Card`. It is the same kind of thing as
            "פרטים טכניים וביקורת" - a long document held closed - so it is now the same
            component, and the chevron and surface come from there rather than from here. */}
        {decision === undefined ? null : (
          <Disclosure summary="הסבר ההחלטות של הגרסה">
            <Card className="bg-cv-surface p-4 shadow-surface">
              <p className="text-support text-cv-text-muted">
                מסמך קריא שמסביר מה נבחר, אילו פערים התקבלו ואילו חריגות נרשמו.
              </p>
              <pre
                className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap rounded-control border border-cv-border bg-cv-surface-sunken p-4 text-support"
                dir="auto"
              >
                {decision.content}
              </pre>
              <Button className="mt-3" onClick={downloadDecision} variant="secondary">
                <Code2 aria-hidden="true" className="size-icon-md" />
                הורדת מסמך ההחלטה
              </Button>
            </Card>
          </Disclosure>
        )}
      </aside>
    </div>
  );
};
