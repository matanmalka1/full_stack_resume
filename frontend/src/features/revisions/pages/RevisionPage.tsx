import { FilePlus2 } from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { ErrorCallout } from "@/app/ErrorCallout";
import { useWorkflowStage, workflowDestinations } from "@/app/WorkflowLandmark";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { PageShell } from "@/ui/PageShell";
import { QueryState } from "@/ui/QueryState";
import { ActiveOperationPanel } from "@/features/applications/components/ActiveOperationPanel";
import { ApplicationBreadcrumbs } from "@/features/applications/components/ApplicationBreadcrumbs";
import { warningDetail, warningTitle } from "@/features/applications/model/applicationLabels";
import { RecruitmentManagerButton } from "@/features/recruitment/components/RecruitmentManagerButton";
import { RevisionRecord } from "../components/RevisionRecord";
import { RevisionSubmissionDialog } from "../components/RevisionSubmissionDialog";
import { RevisionSummary } from "../components/RevisionSummary";
import { useRevisionData } from "../hooks/useRevisionData";
import { useRevisionDraftGeneration } from "../hooks/useRevisionDraftGeneration";

/* One approved revision, addressed by revision rather than Application because the
   immutable record can remain current while work on a newer draft continues. */
const RevisionPageContent = ({ approvedRevisionId }: { approvedRevisionId: string }) => {
  const [submissionOpen, setSubmissionOpen] = useState(false);
  const [submissionRecorded, setSubmissionRecorded] = useState(false);
  const {
    applicationQuery,
    decisionQuery,
    detail,
    displayedWarningCode,
    otherWarnings,
    revision,
    revisionQuery,
    submittedAt,
  } = useRevisionData(approvedRevisionId);
  const { canCreate, createDraft, operation, watch } = useRevisionDraftGeneration(revision, detail);

  useWorkflowStage(
    detail === undefined ? "unknown" : detail.preparation_state,
    revision === undefined ? undefined : workflowDestinations(revision.application_id, detail),
  );

  return (
    <PageShell
      actions={detail === undefined ? null : <RecruitmentManagerButton application={detail.application} />}
      description="הגרסה המאושרת נשארת זמינה גם כאשר העבודה על המועמדות ממשיכה."
      navigation={
        <ApplicationBreadcrumbs
          applicationId={revision?.application_id}
          company={detail?.application.company}
          page="revision"
          revisionLabel={revision?.ready_qualified === false ? "גרסה מאושרת" : "גרסה מוכנה"}
          targetRole={detail?.application.target_role}
        />
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
            {displayedWarningCode === null ? null : (
              <Callout title={warningTitle(displayedWarningCode)} tone="warning">
                {warningDetail(displayedWarningCode, "")}
              </Callout>
            )}
            {otherWarnings.map((warning) => (
              <Callout key={warning.code} title={warningTitle(warning.code)} tone="warning">
                {warningDetail(warning.code, warning.message)}
              </Callout>
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

            <RevisionSummary
              detail={detail}
              onOpenSubmission={() => setSubmissionOpen(true)}
              revision={revision}
              submittedAt={submittedAt}
            />
            <RevisionRecord decision={decisionQuery.data} revision={revision} />
          </>
        )}
      </QueryState>

      {operation === undefined ? null : <ActiveOperationPanel onQueued={watch} operation={operation} />}
      {createDraft.error === null ? null : (
        <ErrorCallout error={createDraft.error} fallbackTitle="לא ניתן ליצור טיוטה חדשה" />
      )}
      {submissionRecorded ? (
        <Callout role="status" title="ההגשה נרשמה" tone="success">
          הגרסה וקובץ ה־PDF המדויקים נוספו להיסטוריית המועמדות.
        </Callout>
      ) : null}
      {revision !== undefined && canCreate ? (
        <div className="flex flex-wrap gap-3">
          <Button
            disabled={detail?.working_draft_state !== "none"}
            onClick={() => createDraft.mutate()}
            pending={createDraft.isPending}
            pendingLabel="יוצר טיוטה…"
            variant="secondary"
          >
            <FilePlus2 aria-hidden="true" className="size-4" />
            יצירת טיוטה חדשה
          </Button>
        </div>
      ) : null}

      {revision === undefined ? null : (
        <RevisionSubmissionDialog
          onClose={() => setSubmissionOpen(false)}
          onRecorded={() => setSubmissionRecorded(true)}
          open={submissionOpen}
          previousSubmittedAt={submittedAt}
          revision={revision}
        />
      )}
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
