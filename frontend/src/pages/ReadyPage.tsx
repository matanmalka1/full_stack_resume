import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { applicationDetailQueryOptions, startDraftGeneration } from "../api/applications";
import { operationQueryKey } from "../api/operations";
import { approvedPreviewSrc, approvedRevisionQueryOptions, recruiterPdfHref } from "../api/revisions";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { PageHeading } from "../ui/PageHeading";
import { SummaryList } from "../ui/SummaryList";
import { TechnicalDetails } from "../ui/TechnicalDetails";
import { ValidationReportView } from "./ValidationReportView";

export const ReadyPage = () => {
  const { approvedRevisionId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  if (approvedRevisionId === undefined) throw new Error("ReadyPage requires approvedRevisionId");
  const revisionQuery = useQuery(approvedRevisionQueryOptions(approvedRevisionId));
  const revision = revisionQuery.data;
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

            <TechnicalDetails>
              <div className="flex flex-col gap-4">
                <SummaryList items={[
                  { term: "גרסה מאושרת", value: revision.id, ltr: true },
                  { term: "ValidationRun", value: revision.validation_run_id, ltr: true },
                  { term: "HTML", value: revision.html_artifact_version_id ?? "חסר", ltr: true },
                  { term: "PDF", value: revision.pdf_artifact_version_id ?? "חסר", ltr: true },
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
        {revision === undefined ? null : (
          <div className="flex flex-wrap gap-3">
            {revision.ready_qualified && revision.pdf_artifact_version_id != null ? (
              <a className={buttonClasses("primary")} href={recruiterPdfHref(revision.id, revision.pdf_artifact_version_id)}>הורדת PDF</a>
            ) : null}
            {hasSources ? (
              <Button disabled={newDraft.isPending || detail?.working_draft_state !== "none"} onClick={() => newDraft.mutate()} variant="secondary">
                {newDraft.isPending ? "יוצר טיוטה…" : "יצירת טיוטה חדשה"}
              </Button>
            ) : (
              <Link className={buttonClasses("secondary")} to={`/applications/${encodeURIComponent(revision.application_id)}`}>חזרה למועמדות ליצירת מקורות עדכניים</Link>
            )}
          </div>
        )}
      </div>
    </Card>
  );
};
