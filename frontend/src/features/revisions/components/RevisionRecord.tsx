import { Lock, type LucideIcon, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import type { ApprovedRevision } from "@/api/contracts";
import { approvedPreviewSrc, type DecisionMarkdownDownload } from "@/api/revisions";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { Disclosure } from "@/ui/Disclosure";
import { DocumentFrame } from "@/ui/DocumentFrame";
import { SummaryList } from "@/ui/SummaryList";
import { DecisionDocument } from "./DecisionDocument";
import { ValidationReportView } from "./ValidationReportView";

interface RevisionRecordProps {
  additionalOptions?: ReactNode;
  decision: DecisionMarkdownDownload | undefined;
  decisionPending?: boolean;
  /* The Application's version history, first in the aside: which version this is and
     how it relates to the others is what a reader places the document by. */
  history?: ReactNode;
  revision: ApprovedRevision;
}

const CardHeading = ({ children, icon: Icon, id }: { children: ReactNode; icon: LucideIcon; id: string }) => (
  <h2 className="flex items-center gap-2 font-semibold text-cv-text" id={id}>
    <Icon aria-hidden="true" className="size-icon-md shrink-0 text-cv-accent" />
    {children}
  </h2>
);

export const RevisionRecord = ({
  additionalOptions,
  decision,
  decisionPending = false,
  history,
  revision,
}: RevisionRecordProps) => {
  const downloadDecision = () => {
    if (decision === undefined) return;
    const href = URL.createObjectURL(new Blob([decision.content], { type: "text/markdown;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = decision.filename;
    /* Firefox ignores a click on a detached anchor, and revoking the URL in the same task
       can cancel the download before the browser has read the blob. */
    anchor.hidden = true;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(href), 0);
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
            className="w-full"
            src={approvedPreviewSrc(revision.id, revision.html_artifact_version_id)}
            title="תצוגה מאושרת של קורות החיים"
          />
        )}
      </div>

      {/* Ordered by what a reader places the document by: its history, whether it holds,
          what can still be done with it, and only then the record and its reasoning. */}
      <aside aria-label="פרטי הגרסה והאימות" className="flex min-w-0 flex-col gap-4">
        {history}

        <Card
          aria-labelledby="ready-validation-heading"
          className="flex flex-col gap-4 rounded-surface bg-cv-surface p-4"
        >
          <CardHeading icon={ShieldCheck} id="ready-validation-heading">
            אימות הגרסה המוכנה
          </CardHeading>
          <ValidationReportView report={revision.ready_validation} />
        </Card>

        {/* Secondary actions belong beside the record they affect. On the wide Ready
            layout this fills the space below validation instead of leaving the aside
            empty while the controls sit below the entire document grid; when the grid
            stacks, the same slot preserves their reading order after validation. */}
        {additionalOptions}

        <Disclosure flush summary="פרטים טכניים וביקורת">
          <Card aria-labelledby="revision-record-heading" className="overflow-x-auto rounded-surface bg-cv-surface p-4">
            <CardHeading icon={Lock} id="revision-record-heading">
              הרשומה הקבועה
            </CardHeading>
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

        {/* The same kind of thing as "פרטים טכניים וביקורת" - a long document held
            closed - so it is the same component, and the chevron and surface come from
            there rather than from here. Opened, it grows with the page instead of
            scrolling inside a fixed box, and it stays present while the record loads or
            is missing, so where the explanation lives never depends on whether it did. */}
        <Disclosure flush summary="הסבר ההחלטות של הגרסה">
          <Card className="rounded-surface bg-cv-surface p-4">
            <DecisionDocument decision={decision} onDownload={downloadDecision} pending={decisionPending} />
          </Card>
        </Disclosure>
      </aside>
    </div>
  );
};
