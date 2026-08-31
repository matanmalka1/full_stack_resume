import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { applicationDetailQueryOptions, startDraftGeneration } from "../api/applications";
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
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { PageHeading } from "../ui/PageHeading";
import { SummaryList } from "../ui/SummaryList";
import { TechnicalDetails } from "../ui/TechnicalDetails";
import { Dialog } from "../ui/Dialog";
import { Field } from "../ui/Field";
import { TextInput } from "../ui/TextInput";
import { ValidationReportView } from "./ValidationReportView";

export const ReadyPage = () => {
  const { approvedRevisionId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [submissionOpen, setSubmissionOpen] = useState(false);
  const [submittedAt, setSubmittedAt] = useState(() => {
    const now = new Date();
    return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
  });
  if (approvedRevisionId === undefined) throw new Error("ReadyPage requires approvedRevisionId");
  const revisionQuery = useQuery(approvedRevisionQueryOptions(approvedRevisionId));
  const revision = revisionQuery.data;
  const decisionQuery = useQuery({
    ...decisionMarkdownQueryOptions(
      approvedRevisionId,
      revision?.application_id ?? "",
    ),
    enabled: revision !== undefined,
  });
  const applicationQuery = useQuery({
    ...applicationDetailQueryOptions(revision?.application_id ?? ""),
    enabled: revision !== undefined,
  });
  const detail = applicationQuery.data;
  useWorkflowStage(detail === undefined ? "unknown" : detail.preparation_state);
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
    onSuccess: ({ operation, operationPath }) => {
      queryClient.setQueryData(operationQueryKey(operation.id), operation);
      void navigate(operationPath);
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
    onSuccess: (result) => {
      setSubmissionOpen(false);
      queryClient.setQueryData(["latest-submission", approvedRevisionId], result);
      if (revision !== undefined) {
        void queryClient.invalidateQueries({
          queryKey: applicationDetailQueryOptions(revision.application_id).queryKey,
        });
      }
      void queryClient.invalidateQueries({ queryKey: ["applications"] });
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
      warning.code !== "READY_REVISION_FOR_OLDER_SNAPSHOT" &&
      warning.code !== "READY_REVISION_FOR_OLDER_ANALYSIS",
  );
  const submittedAtValid = !Number.isNaN(new Date(submittedAt).getTime());
  const downloadDecision = () => {
    if (decisionQuery.data === undefined) return;
    const href = URL.createObjectURL(
      new Blob([decisionQuery.data.content], { type: "text/markdown;charset=utf-8" }),
    );
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = decisionQuery.data.filename;
    anchor.click();
    URL.revokeObjectURL(href);
  };

  return (
    <Card aria-labelledby="route-heading">
      <PageHeading id="route-heading" description="הגרסה המאושרת נשארת זמינה גם כאשר העבודה על המועמדות ממשיכה.">
        קורות החיים מוכנים
      </PageHeading>
      <div className="mt-6 flex flex-col gap-6">
        {revisionQuery.error === null && applicationQuery.error === null ? null : (
          <ErrorCallout
            error={revisionQuery.error ?? applicationQuery.error}
            fallbackDetail="הפנייה לשרת נכשלה."
            fallbackTitle="לא ניתן לטעון את הגרסה המוכנה"
          />
        )}
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
          <Callout title="קיימת טיוטה חדשה יותר" tone="warning">היא אינה משנה את הגרסה המוכנה המוצגת כאן.</Callout>
        ) : null}
        {revision !== undefined && !revision.ready_qualified ? (
          <Callout title="הגרסה עדיין אינה מוכנה למסירה" tone="blocker">פרטי בדיקת ה־Ready מוצגים בהמשך.</Callout>
        ) : null}
        {revision === undefined ? <p className="text-body text-cv-text-muted">טוען את הגרסה…</p> : (
          <>
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

            {/* What a person needs about the version, in words. The identifiers behind
                them stay in the collapsed block below. */}
            <SummaryList items={[
              { term: "מספר גרסה", value: revision.version_number, ltr: true },
              { term: "קובץ HTML", value: revision.html_artifact_version_id == null ? "חסר" : "קיים" },
              { term: "קובץ PDF", value: revision.pdf_artifact_version_id == null ? "חסר" : "קיים" },
            ]} />

            <ValidationReportView report={revision.ready_validation} />

            {decisionQuery.data === undefined ? null : (
              <details className="rounded-surface border border-cv-border bg-cv-surface-muted p-4">
                <summary className="cursor-pointer font-semibold text-cv-text">
                  הסבר ההחלטות של הגרסה
                </summary>
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

            <TechnicalDetails>
              <div className="flex flex-col gap-4">
                <SummaryList items={[
                  { term: "גרסה מאושרת", value: revision.id, ltr: true },
                  { term: "ValidationRun", value: revision.validation_run_id, ltr: true },
                  { term: "HTML", value: revision.html_artifact_version_id ?? "חסר", ltr: true },
                  { term: "PDF", value: revision.pdf_artifact_version_id ?? "חסר", ltr: true },
                  { term: "Decision Markdown", value: decisionQuery.data?.content_hash ?? "לא נטען", ltr: true },
                ]} />
                <div>
                  <p className="mb-2 font-semibold text-cv-text">מקור האישור</p>
                  <pre className="overflow-auto text-support">{JSON.stringify(revision.decision_provenance, null, 2)}</pre>
                </div>
              </div>
            </TechnicalDetails>
          </>
        )}
        {newDraft.error === null ? null : (
          <ErrorCallout
            error={newDraft.error}
            fallbackDetail="הפנייה לשרת נכשלה."
            fallbackTitle="לא ניתן ליצור טיוטה חדשה"
          />
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
              <a className={buttonClasses("primary")} href={recruiterPdfHref(revision.id, revision.pdf_artifact_version_id)}>הורדת PDF</a>
            ) : null}
            {revision.ready_qualified && revision.pdf_artifact_version_id != null ? (
              <Button onClick={() => setSubmissionOpen(true)} variant="secondary">
                רישום הגשת הגרסה הזו
              </Button>
            ) : null}
            {hasSources ? (
              <Button disabled={newDraft.isPending || detail?.working_draft_state !== "none"} onClick={() => newDraft.mutate()} variant="secondary">
                {newDraft.isPending ? "יוצר טיוטה…" : "יצירת טיוטה חדשה"}
              </Button>
            ) : null}
            {/* The way back, offered whether or not a new draft can be started here.

                It used to appear only when the sources were stale - as the fallback for a
                missing "new draft" button rather than as an exit - which left the ordinary
                case, a Ready revision with current sources, with no link off the screen at
                all. Ready is the end of the workflow, not the end of the Application: the
                approved files stay downloadable while work on the Application continues,
                so the screen that says so has to be leaveable. */}
            <Link className={buttonClasses("secondary")} to={`/applications/${encodeURIComponent(revision.application_id)}`}>
              {hasSources ? "חזרה למועמדות" : "חזרה למועמדות ליצירת מקורות עדכניים"}
            </Link>
          </div>
        )}
      </div>
      <Dialog
        dismissible={false}
        footer={
          <>
            <Button onClick={() => setSubmissionOpen(false)} variant="secondary">
              חזרה
            </Button>
            <Button
              disabled={submission.isPending || !submittedAtValid}
              onClick={() => submission.mutate()}
            >
              {submission.isPending ? "רושם…" : "אישור ורישום ההגשה"}
            </Button>
          </>
        }
        headingId="submission-dialog-heading"
        onClose={() => setSubmissionOpen(false)}
        open={submissionOpen}
        title="רישום הגשה קבועה"
      >
        <p className="mb-4">
          הרישום קבוע ומתייחס לגרסה ולקובץ ה־PDF המוצגים במסך הזה. הוא לא יפתור גרסה
          אחרת או קובץ אחר בזמן השמירה.
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
    </Card>
  );
};
