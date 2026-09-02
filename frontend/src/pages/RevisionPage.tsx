import { Link, useParams } from "react-router-dom";

import { approvedPreviewSrc, recruiterPdfHref } from "../api/revisions";
import { ErrorCallout } from "../app/ErrorCallout";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Dialog } from "../ui/Dialog";
import { Field } from "../ui/Field";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { SummaryList } from "../ui/SummaryList";
import { TextInput } from "../ui/TextInput";
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
            {/* The document is the point of this screen. It is presented as a page on the
                canvas - full width, paper elevation, nothing competing beside it - rather
                than as one item in a list of identifiers. */}
            {revision.html_artifact_version_id == null ? null : (
              <iframe
                className="h-[46rem] w-full rounded-surface border border-cv-border bg-cv-surface-raised shadow-document"
                sandbox=""
                src={approvedPreviewSrc(revision.id, revision.html_artifact_version_id)}
                title="תצוגה מאושרת של קורות החיים"
              />
            )}

            {/* What a person needs about the version, in words. */}
            <SummaryList
              items={[
                { term: "מספר גרסה", value: revision.version_number, ltr: true },
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

            <ValidationReportView report={revision.ready_validation} />

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
                  הורדת מסמך ההחלטה
                </Button>
              </details>
            )}
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
          {revision.ready_qualified && revision.pdf_artifact_version_id != null ? (
            <a
              className={buttonClasses("primary")}
              href={recruiterPdfHref(revision.id, revision.pdf_artifact_version_id)}
            >
              הורדת PDF
            </a>
          ) : null}
          {revision.ready_qualified && revision.pdf_artifact_version_id != null ? (
            <Button onClick={() => setSubmissionOpen(true)} variant="secondary">
              רישום הגשת הגרסה הזו
            </Button>
          ) : null}
          {hasSources ? (
            <Button
              disabled={detail?.working_draft_state !== "none"}
              onClick={() => newDraft.mutate()}
              pending={newDraft.isPending}
              pendingLabel="יוצר טיוטה…"
              variant="secondary"
            >
              יצירת טיוטה חדשה
            </Button>
          ) : null}
          {/* The way back, offered whether or not a new draft can be started here.

                It used to appear only when the sources were stale - as the fallback for a
                missing "new draft" button rather than as an exit - which left the ordinary
                case, a Ready revision with current sources, with no link off the screen at
                all. Ready is the end of the workflow, not the end of the Application: the
                approved files stay downloadable while work on the Application continues,
                so the screen that says so has to be leaveable. */}
          <Link
            className={buttonClasses("secondary")}
            to={`/applications/${encodeURIComponent(revision.application_id)}`}
          >
            {hasSources ? "חזרה למועמדות" : "חזרה למועמדות ליצירת מקורות עדכניים"}
          </Link>
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
