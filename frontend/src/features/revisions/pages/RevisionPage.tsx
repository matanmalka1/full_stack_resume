import { ArrowRight, Download, FilePlus2, Send } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { routePaths } from "@/app/routePaths";
import { recruiterPdfHref } from "@/api/revisions";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { PageShell } from "@/ui/PageShell";
import { QueryState } from "@/ui/QueryState";
import { ActiveOperationPanel } from "@/features/operations";
import { applicationLabel } from "@/features/applications";
import { CommitBar, NEXT_STEP_LABEL, PreparationWorkflowSteps } from "@/features/preparation";
import { warningDetail, warningTitle } from "@/features/preparation";
import { RevisionRecord } from "../components/RevisionRecord";
import { RevisionSubmissionDialog } from "../components/RevisionSubmissionDialog";
import { RevisionSummary } from "../components/RevisionSummary";
import { useRevisionData } from "../api/queries";
import { useRevisionDraftGeneration } from "../api/mutations";

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

  /* One step back from "מוכן" is the draft it was approved from - the editor where a
     correction is actually made. With no draft to return to, the step behind it is the
     preparation screen, which is where a new one is started. Never the board: leaving the
     flow is the shell's link, not the wizard's. */
  const applicationId = revision?.application_id ?? null;
  const draftReachable = detail?.active_working_draft_id != null || detail?.preparation_state === "approved";
  const backLink =
    applicationId === null ? undefined : (
      <Link
        className={buttonClasses("ghost")}
        to={draftReachable ? routePaths.draft(applicationId) : routePaths.application(applicationId)}
      >
        <ArrowRight aria-hidden="true" className="size-4" />
        {draftReachable ? "חזרה לעורך הטיוטה" : "חזרה להכנת קורות החיים"}
      </Link>
    );

  /* What the finished CV is for, in the order the step offers it. A revision that did not
     qualify has no PDF to hand over, so the step's action is the way back to fixing it -
     which is the back link itself, and the bar draws nothing rather than a primary that
     repeats it. */
  const recruiterPdfArtifactId = revision?.ready_qualified === true ? revision.pdf_artifact_version_id : null;
  const newDraftButton = !canCreate ? null : (
    <Button
      disabled={detail?.working_draft_state !== "none"}
      key="new-draft"
      onClick={() => createDraft.mutate()}
      pending={createDraft.isPending}
      pendingLabel="יוצר טיוטה…"
      variant="secondary"
    >
      <FilePlus2 aria-hidden="true" className="size-4" />
      יצירת טיוטה חדשה
    </Button>
  );
  const nextStep =
    revision === undefined
      ? null
      : recruiterPdfArtifactId == null
        ? newDraftButton === null
          ? null
          : { note: "הגרסה אינה עומדת בתנאי המסירה. דוח האימות מפרט את החסימות.", primary: newDraftButton }
        : {
            note:
              submittedAt === null
                ? "הקובץ מוכן להורדה ולמסירה למגייס."
                : "הגרסה כבר רשומה כמוגשת. אפשר לרשום הגשה נוספת של אותה גרסה.",
            primary: (
              <a className={buttonClasses("primary")} href={recruiterPdfHref(revision.id, recruiterPdfArtifactId)}>
                <Download aria-hidden="true" className="size-4" />
                הורדת PDF
              </a>
            ),
            /* The button says what pressing it would do next, which is not the same
               sentence once a submission is on record. It stayed "רישום הגשת הגרסה הזו"
               after the submission was recorded, so the screen offered the action it had
               just completed as though nothing had happened. */
            secondary: [
              <Button key="submission" onClick={() => setSubmissionOpen(true)} variant="secondary">
                <Send aria-hidden="true" className="size-4" />
                {submittedAt === null ? "רישום הגשת הגרסה הזו" : "רישום הגשה נוספת"}
              </Button>,
              newDraftButton,
            ].filter((node) => node !== null),
          };

  return (
    <PageShell
      description="הגרסה המאושרת נשארת זמינה גם כאשר העבודה על המועמדות ממשיכה."
      eyebrow={
        detail === undefined ? undefined : (
          <span dir="auto">{applicationLabel(detail.application.company, detail.application.target_role)}</span>
        )
      }
      landmark={<PreparationWorkflowSteps applicationId={revision?.application_id} detail={detail} />}
      measure="wizard"
      /* The last stage's name, qualified only where the record does not actually meet it:
         a revision that is approved but not deliverable is not "מוכן", and saying so in
         the heading is the difference between the two the summary below also draws. */
      title={revision?.ready_qualified === false ? "גרסה מאושרת" : "מוכן למסירה"}
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

            <RevisionSummary detail={detail} revision={revision} submittedAt={submittedAt} />
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
      {/* The ready step's own bar, the same surface the two steps before it close with:
          the way back on one edge, what to do with the finished CV on the other. The
          download used to sit in the summary card's corner and creating a new draft was a
          loose button at the foot of the page - two commands in two places, neither of
          them where the previous steps had taught the reader to look. */}
      {nextStep === null ? null : (
        <CommitBar
          back={backLink}
          label={NEXT_STEP_LABEL}
          primary={
            <>
              {nextStep.secondary === undefined ? null : (
                <div className="flex flex-wrap gap-3">{nextStep.secondary}</div>
              )}
              {nextStep.primary}
            </>
          }
        >
          <p className="text-support leading-6 text-cv-text-muted" dir="auto">
            {nextStep.note}
          </p>
        </CommitBar>
      )}

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
