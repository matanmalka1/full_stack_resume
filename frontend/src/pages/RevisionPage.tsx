import { Code2, Download, FileCheck2, FilePlus2, Lock, Send, ShieldCheck } from "lucide-react";
import { useParams } from "react-router-dom";

import { approvedPreviewSrc, recruiterPdfHref } from "../api/revisions";
import { ErrorCallout } from "../app/ErrorCallout";
import { BackLink } from "../ui/BackLink";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { Dialog } from "../ui/Dialog";
import { Field } from "../ui/Field";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { StatusBadge } from "../ui/StatusBadge";
import { SummaryList } from "../ui/SummaryList";
import { TextInput } from "../ui/TextInput";
import { formatDateTime } from "../ui/formatDateTime";
import { useRevisionPageState } from "./revision/useRevisionPageState";
import { ValidationReportView } from "./revision/ValidationReportView";

/* One approved revision: its document, its files, and the record of its submission.

   It is addressed by the revision rather than by the Application, and that is the whole
   reason it stays a screen of its own rather than becoming a state of the editor. An
   approved revision is immutable, the list and the action plan both link to a specific
   one, and `latest_ready_revision_id` can name a revision while a newer draft is already
   in progress - so a screen keyed by the Application would answer those links with a
   different record than the one they named. */
interface RevisionPageContentProps {
  approvedRevisionId: string;
}

const RevisionPageContent = ({ approvedRevisionId }: RevisionPageContentProps) => {
  const {
    applicationQuery,
    decisionQuery,
    detail,
    downloadDecision,
    hasSources,
    historicalContext,
    newDraft,
    operationPanel,
    otherWarnings,
    revision,
    revisionQuery,
    setSubmissionOpen,
    setSubmittedAt,
    submission,
    submissionOpen,
    submittedAt,
    submittedAtValid,
  } = useRevisionPageState(approvedRevisionId);

  /* The heading follows the revision, not the route. It read "קורות החיים מוכנים"
     unconditionally, directly above the blocker this screen shows for a revision
     that is not `ready_qualified` - the masthead asserting the one thing the body
     was there to deny. */
  return (
    <PageShell
      description="הגרסה המאושרת נשארת זמינה גם כאשר העבודה על המועמדות ממשיכה."
      navigation={
        revision === undefined ? undefined : (
          <BackLink label="חזרה למועמדות" to={`/applications/${encodeURIComponent(revision.application_id)}`}>
            {hasSources ? "חזרה למועמדות" : "חזרה למועמדות ליצירת מקורות עדכניים"}
          </BackLink>
        )
      }
      title={revision?.ready_qualified === false ? "גרסה מאושרת" : "קורות החיים מוכנים"}
    >
      <QueryState
        error={revisionQuery.error ?? applicationQuery.error}
        fallbackTitle="לא ניתן לטעון את הגרסה המוכנה"
        loading={revision === undefined}
        loadingLabel="טוען את הגרסה…"
      >
        {revision === undefined ? null : (
          <>
            {decisionQuery.error === null ? null : (
              <ErrorCallout
                error={decisionQuery.error}
                fallbackDetail="הגרסה עצמה נשארה זמינה; רק מסמך הסבר ההחלטה לא נטען."
                fallbackTitle="לא ניתן לטעון את הסבר ההחלטה"
              />
            )}
            {historicalContext === null ? null : (
              <Callout title="הגרסה היסטורית בהקשר הפעיל" tone="warning">
                {historicalContext}
              </Callout>
            )}
            {otherWarnings?.map((warning) => (
              <Callout key={warning.code} title={warning.message} tone="warning" />
            ))}
            {detail?.newer_draft_in_progress ? (
              <Callout title="קיימת טיוטה חדשה יותר" tone="warning">
                היא אינה משנה את הגרסה המוכנה המוצגת כאן.
              </Callout>
            ) : null}
            {!revision.ready_qualified ? (
              <Callout title="הגרסה עדיין אינה מוכנה למסירה" tone="blocker">
                דוח האימות שמתחת מפרט את החסימות.
              </Callout>
            ) : null}
            <Card aria-labelledby="revision-summary-heading" className="bg-cv-surface p-4 shadow-surface sm:p-5">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="flex min-w-0 items-start gap-3">
                  <span className="grid size-11 shrink-0 place-items-center rounded-pill bg-cv-success-soft text-cv-success">
                    <FileCheck2 aria-hidden="true" className="size-5" />
                  </span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-heading-sm font-bold text-cv-text" id="revision-summary-heading">
                        {revision.ready_qualified ? "גרסה מוכנה למסירה" : "גרסה מאושרת וקבועה"}
                      </h2>
                      <StatusBadge tone={revision.ready_qualified ? "success" : "warning"}>
                        {revision.ready_qualified ? "Ready" : "ממתינה לקבצים תקינים"}
                      </StatusBadge>
                    </div>
                    {detail === undefined ? null : (
                      <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                        {detail.application.company} · {detail.application.target_role}
                      </p>
                    )}
                    <p className="mt-1 text-support text-cv-text-muted">
                      אושרה {formatDateTime(revision.approved_at, "short")} · גרסה {revision.version_number}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {revision.ready_qualified && revision.pdf_artifact_version_id != null ? (
                    <a
                      className={buttonClasses("primary")}
                      href={recruiterPdfHref(revision.id, revision.pdf_artifact_version_id)}
                    >
                      <Download aria-hidden="true" className="size-4" />
                      הורדת PDF
                    </a>
                  ) : null}
                  {revision.ready_qualified && revision.pdf_artifact_version_id != null ? (
                    <Button onClick={() => setSubmissionOpen(true)} variant="secondary">
                      <Send aria-hidden="true" className="size-4" />
                      רישום הגשת הגרסה הזו
                    </Button>
                  ) : null}
                </div>
              </div>
            </Card>

            <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(19rem,1fr)]">
              {/* The server-rendered document is the authoritative presentation. No
                  candidate wording or artifact metadata is reconstructed in React. */}
              <div className="min-w-0">
                {revision.html_artifact_version_id == null ? (
                  <Callout title="עדיין אין קובץ HTML לתצוגה" tone="neutral">
                    הגרסה המאושרת נשמרה, אך תצוגת המסמך תופיע רק לאחר יצירת הארטיפקט הרשום.
                  </Callout>
                ) : (
                  <iframe
                    className="h-[46rem] w-full rounded-surface border border-cv-border bg-cv-surface-raised shadow-document"
                    sandbox=""
                    src={approvedPreviewSrc(revision.id, revision.html_artifact_version_id)}
                    title="תצוגה מאושרת של קורות החיים"
                  />
                )}
              </div>

              <aside aria-label="פרטי הגרסה והאימות" className="flex min-w-0 flex-col gap-6">
                <Card
                  aria-labelledby="revision-record-heading"
                  className="overflow-x-auto bg-cv-surface p-4 shadow-surface"
                >
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
                      {
                        term: "קובץ HTML",
                        value: revision.html_artifact_version_id == null ? "חסר" : "קיים",
                      },
                      {
                        term: "קובץ PDF",
                        value: revision.pdf_artifact_version_id == null ? "חסר" : "קיים",
                      },
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

                {decisionQuery.data === undefined ? null : (
                  <details className="rounded-surface border border-cv-border bg-cv-surface-muted p-4">
                    <summary className="cursor-pointer font-semibold text-cv-text">הסבר ההחלטות של הגרסה</summary>
                    <p className="mt-2 text-support text-cv-text-muted">
                      מסמך קריא שמסביר מה נבחר, אילו פערים התקבלו ואילו חריגות נרשמו.
                    </p>
                    <pre
                      className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap rounded-control border border-cv-border bg-cv-surface p-4 text-support"
                      dir="auto"
                    >
                      {decisionQuery.data.content}
                    </pre>
                    <Button className="mt-3" onClick={downloadDecision} variant="secondary">
                      <Code2 aria-hidden="true" className="size-4" />
                      הורדת מסמך ההחלטה
                    </Button>
                  </details>
                )}
              </aside>
            </div>
          </>
        )}
      </QueryState>
      {operationPanel}
      {newDraft.error === null ? null : (
        <ErrorCallout error={newDraft.error} fallbackTitle="לא ניתן ליצור טיוטה חדשה" />
      )}
      {submission.error === null ? null : (
        <ErrorCallout
          error={submission.error}
          fallbackDetail="ההגשה לא נרשמה וההיסטוריה לא השתנתה."
          fallbackTitle="לא ניתן לרשום את ההגשה"
        />
      )}
      {submission.isSuccess ? (
        <Callout role="status" title="ההגשה נרשמה" tone="success">
          הגרסה וקובץ ה־PDF המדויקים נוספו להיסטוריית המועמדות.
        </Callout>
      ) : null}
      {revision === undefined ? null : (
        <div className="flex flex-wrap gap-3">
          {hasSources ? (
            <Button
              disabled={detail?.working_draft_state !== "none"}
              onClick={() => newDraft.mutate()}
              pending={newDraft.isPending}
              pendingLabel="יוצר טיוטה…"
              variant="secondary"
            >
              <FilePlus2 aria-hidden="true" className="size-4" />
              יצירת טיוטה חדשה
            </Button>
          ) : null}
        </div>
      )}
      <Dialog
        dismissible={false}
        footer={
          <>
            <Button onClick={() => setSubmissionOpen(false)} variant="secondary">
              חזרה
            </Button>
            <Button
              disabled={!submittedAtValid}
              onClick={() => submission.mutate()}
              pending={submission.isPending}
              pendingLabel="רושם…"
            >
              אישור ורישום ההגשה
            </Button>
          </>
        }
        headingId="submission-dialog-heading"
        onClose={() => setSubmissionOpen(false)}
        open={submissionOpen}
        title="רישום הגשה קבועה"
      >
        <p className="mb-4">
          הרישום קבוע ומתייחס לגרסה ולקובץ ה־PDF המוצגים במסך הזה. הוא לא יפתור גרסה אחרת או קובץ אחר בזמן השמירה.
        </p>
        <Field label="מועד ההגשה">
          {(control) => (
            <TextInput
              {...control}
              onChange={(event) => setSubmittedAt(event.target.value)}
              required
              type="datetime-local"
              value={submittedAt}
            />
          )}
        </Field>
      </Dialog>
    </PageShell>
  );
};

export const RevisionPage = () => {
  const { revisionId } = useParams();

  if (revisionId === undefined) {
    throw new Error("RevisionPage requires a revisionId route parameter");
  }

  return <RevisionPageContent approvedRevisionId={revisionId} />;
};
