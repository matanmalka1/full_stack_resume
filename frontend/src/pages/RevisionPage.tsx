import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { applicationDetailQueryOptions, applicationListQueryPrefix, startDraftGeneration } from "../api/applications";
import { operationQueryKey } from "../api/operations";
import {
  approvedPreviewSrc,
  approvedRevisionQueryOptions,
  decisionMarkdownQueryOptions,
  recruiterPdfHref,
} from "../api/revisions";
import { recordInternalSubmission } from "../api/tracking";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { useWatchedOperation } from "../hooks/useWatchedOperation";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { SummaryList } from "../ui/SummaryList";
import { Dialog } from "../ui/Dialog";
import { Field } from "../ui/Field";
import { TextInput } from "../ui/TextInput";
import { localDateTimeInputValue } from "./revision/submissionDate";
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
  const queryClient = useQueryClient();
  const [submissionOpen, setSubmissionOpen] = useState(false);
  const [submittedAt, setSubmittedAt] = useState(() => localDateTimeInputValue(new Date()));
  const revisionQuery = useQuery(approvedRevisionQueryOptions(approvedRevisionId));
  const revision = revisionQuery.data;
  const decisionQuery = useQuery({
    ...decisionMarkdownQueryOptions(approvedRevisionId, revision?.application_id ?? ""),
    enabled: revision !== undefined,
  });
  const applicationQuery = useQuery({
    ...applicationDetailQueryOptions(revision?.application_id ?? ""),
    enabled: revision !== undefined,
  });
  const detail = applicationQuery.data;
  useWorkflowStage(detail === undefined ? "unknown" : detail.preparation_state);
  /* The same watch the Application screen and the editor keep. This screen queues one
     command - a new draft from the approved revision - and reports it beside the files
     rather than sending the reader to a screen that holds neither. */
  const { panel: operationPanel, watch } = useWatchedOperation(revision?.application_id ?? "", detail);
  const newDraftKey = useMemo(
    () =>
      `revision-draft:${approvedRevisionId}:${detail?.active_analysis_id ?? "none"}:${detail?.active_selection_plan_id ?? "none"}`,
    [approvedRevisionId, detail?.active_analysis_id, detail?.active_selection_plan_id],
  );
  const newDraft = useMutation({
    mutationFn: async () => {
      if (revision === undefined || detail?.active_analysis_id == null || detail.active_selection_plan_id == null) {
        throw new Error("No active compatible analysis and selection plan");
      }
      return startDraftGeneration(
        revision.application_id,
        detail.active_analysis_id,
        detail.active_selection_plan_id,
        newDraftKey,
        { parentRevisionId: revision.id },
      );
    },
    /* Reported in place rather than followed. Generating a new draft from a Ready
       revision used to navigate to the Operation's own screen, which handed the user a
       progress line and then a link back to the Application - so the approved files they
       were looking at went off screen, and the draft the work produced was reached by a
       third step. The watch below reports the run here and the projection names the draft
       when it exists. */
    onSuccess: ({ operation }) => {
      queryClient.setQueryData(operationQueryKey(operation.id), operation);
      watch(operation.id);
    },
  });
  const submission = useMutation({
    mutationFn: async () => {
      if (revision === undefined || revision.pdf_artifact_version_id == null) {
        throw new Error("Submission requires the exact Ready revision and PDF");
      }
      return recordInternalSubmission(revision.application_id, {
        approved_revision_id: revision.id,
        pdf_artifact_version_id: revision.pdf_artifact_version_id,
        submitted_at: new Date(submittedAt).toISOString(),
        metadata: {},
      });
    },
    onSuccess: () => {
      setSubmissionOpen(false);
      if (revision !== undefined) {
        void queryClient.invalidateQueries({
          queryKey: applicationDetailQueryOptions(revision.application_id).queryKey,
        });
      }
      void queryClient.invalidateQueries({ queryKey: applicationListQueryPrefix });
    },
  });
  const hasSources = detail?.active_analysis_id != null && detail.active_selection_plan_id != null;
  const historicalContext =
    revision === undefined || detail === undefined
      ? null
      : revision.job_snapshot_id !== detail.active_job_snapshot_id
        ? "הגרסה המוכנה שייכת לתצלום משרה ישן יותר מהתצלום הפעיל. הקבצים שלה נשארים תקינים וזמינים להורדה."
        : revision.job_analysis_id !== detail.active_analysis_id
          ? "הגרסה המוכנה שייכת לניתוח ישן יותר מהניתוח הפעיל. הקבצים שלה נשארים תקינים וזמינים להורדה."
          : null;
  const otherWarnings = detail?.warnings.filter(
    (warning) =>
      warning.code !== "READY_REVISION_FOR_OLDER_SNAPSHOT" && warning.code !== "READY_REVISION_FOR_OLDER_ANALYSIS",
  );
  const submittedAtValid = !Number.isNaN(new Date(submittedAt).getTime());
  const downloadDecision = () => {
    if (decisionQuery.data === undefined) return;
    const href = URL.createObjectURL(new Blob([decisionQuery.data.content], { type: "text/markdown;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = decisionQuery.data.filename;
    anchor.click();
    URL.revokeObjectURL(href);
  };

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
