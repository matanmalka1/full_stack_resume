import { FilePlus2 } from "lucide-react";
import { useParams } from "react-router-dom";

import { ErrorCallout } from "../app/ErrorCallout";
import { appRoutes } from "../app/appRoutes";
import { BackLink } from "../ui/BackLink";
import { Button } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { ActiveOperationPanel } from "./ActiveOperationPanel";
import { warningDetail, warningTitle } from "./application/applicationLabels";
import { RevisionRecord } from "./revision/RevisionRecord";
import { RevisionSubmissionDialog } from "./revision/RevisionSubmissionDialog";
import { RevisionSummary } from "./revision/RevisionSummary";
import { useRevisionPageState } from "./revision/useRevisionPageState";

/* One approved revision, addressed by revision rather than Application because the
   immutable record can remain current while work on a newer draft continues. */
const RevisionPageContent = ({ approvedRevisionId }: { approvedRevisionId: string }) => {
  const state = useRevisionPageState(approvedRevisionId);
  const { detail, revision } = state;

  return (
    <PageShell
      description="הגרסה המאושרת נשארת זמינה גם כאשר העבודה על המועמדות ממשיכה."
      navigation={
        revision === undefined ? undefined : (
          <BackLink label="חזרה למועמדות" to={appRoutes.application(revision.application_id)}>
            {state.hasSources ? "חזרה למועמדות" : "חזרה למועמדות ליצירת מקורות עדכניים"}
          </BackLink>
        )
      }
      title={revision?.ready_qualified === false ? "גרסה מאושרת" : "קורות החיים מוכנים"}
    >
      <QueryState
        error={state.revisionQuery.error ?? state.applicationQuery.error}
        fallbackTitle="לא ניתן לטעון את הגרסה המוכנה"
        loading={revision === undefined}
        loadingLabel="טוען את הגרסה…"
      >
        {revision === undefined ? null : (
          <>
            {state.decisionQuery.error === null ? null : (
              <ErrorCallout
                error={state.decisionQuery.error}
                fallbackDetail="הגרסה עצמה נשארה זמינה; רק מסמך הסבר ההחלטה לא נטען."
                fallbackTitle="לא ניתן לטעון את הסבר ההחלטה"
              />
            )}
            {state.displayedRevisionWarningCode === null ? null : (
              <Callout title={warningTitle(state.displayedRevisionWarningCode)} tone="warning">
                {warningDetail(state.displayedRevisionWarningCode, "")}
              </Callout>
            )}
            {state.otherWarnings?.map((warning) => (
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
              onOpenSubmission={() => state.setSubmissionOpen(true)}
              revision={revision}
            />
            <RevisionRecord
              decision={state.decisionQuery.data}
              onDownloadDecision={state.downloadDecision}
              revision={revision}
            />
          </>
        )}
      </QueryState>

      {state.operation === undefined ? null : (
        <ActiveOperationPanel onQueued={state.watch} operation={state.operation} />
      )}
      {state.newDraft.error === null ? null : (
        <ErrorCallout error={state.newDraft.error} fallbackTitle="לא ניתן ליצור טיוטה חדשה" />
      )}
      {state.submission.error === null ? null : (
        <ErrorCallout
          error={state.submission.error}
          fallbackDetail="ההגשה לא נרשמה וההיסטוריה לא השתנתה."
          fallbackTitle="לא ניתן לרשום את ההגשה"
        />
      )}
      {state.submission.isSuccess ? (
        <Callout role="status" title="ההגשה נרשמה" tone="success">
          הגרסה וקובץ ה־PDF המדויקים נוספו להיסטוריית המועמדות.
        </Callout>
      ) : null}
      {revision !== undefined && state.hasSources ? (
        <div className="flex flex-wrap gap-3">
          <Button
            disabled={detail?.working_draft_state !== "none"}
            onClick={() => state.newDraft.mutate()}
            pending={state.newDraft.isPending}
            pendingLabel="יוצר טיוטה…"
            variant="secondary"
          >
            <FilePlus2 aria-hidden="true" className="size-4" />
            יצירת טיוטה חדשה
          </Button>
        </div>
      ) : null}

      <RevisionSubmissionDialog
        onClose={() => state.setSubmissionOpen(false)}
        onSubmit={() => state.submission.mutate()}
        onSubmittedAtChange={state.setSubmittedAt}
        open={state.submissionOpen}
        pending={state.submission.isPending}
        submittedAt={state.submittedAt}
        submittedAtValid={state.submittedAtValid}
      />
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
