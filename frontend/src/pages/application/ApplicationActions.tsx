import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactElement, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  applicationDetailQueryKey,
  replaceWorkingDraft,
  startAnalysis,
  startDraftGeneration,
} from "../../api/applications";
import type { ApplicationDetail } from "../../api/contracts";
import { archiveWorkingDraft, workingDraftQueryKey, workingDraftQueryOptions } from "../../api/drafts";
import { executionProvider, settingsQueryOptions } from "../../api/settings";
import { type QueuedOperation, operationQueryKey } from "../../api/operations";
import { ErrorCallout } from "../../app/ErrorCallout";
import { ActionBar } from "../../ui/ActionBar";
import { Button, buttonClasses } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Checkbox } from "../../ui/Checkbox";
import { Dialog } from "../../ui/Dialog";
import { applicationActionPlan } from "./applicationActionPlan";
import { actionLabel } from "./applicationLabels";

interface ApplicationActionsProps {
  detail: ApplicationDetail;
  /* What this component just queued. The projection reports an Operation only on its next
     read, so without this the panel would appear a poll later than the press that caused
     it - and a command that failed before the worker picked it up might never be reported
     at all. The accepted `202` is the earliest and most certain answer, so it is handed
     straight to the screen that shows it. */
  onQueued: (operationId: string) => void;
}

/* A.1: the actions come from the projection, read by `applicationActionPlan`. What is left
   here is the two commands this screen sends and the bar it renders them in. */
export const ApplicationActions = ({ detail, onQueued }: ApplicationActionsProps) => {
  const queryClient = useQueryClient();
  /* App owns the live settings read. This subscription consumes that cache without
     opening one request per action panel; isolated renders retain the safe deterministic
     default until a shell-provided value exists. */
  const settingsQuery = useQuery({ ...settingsQueryOptions, enabled: false });
  const settings = settingsQuery.data?.settings;
  const provider = executionProvider(settings);
  const snapshotId = detail.active_job_snapshot_id;
  const plan = applicationActionPlan(detail);
  /* One key per snapshot: an answer that never arrived can be sent again without
     queueing a second analysis of the same posting. */
  const analyzeKey = useMemo(() => crypto.randomUUID(), [snapshotId]);
  /* One key per source pair, for the same reason: a resent generate for the same analysis
     and plan is the same command, and a different pair is a different one. */
  const draftKey = useMemo(
    () => crypto.randomUUID(),
    [plan.createDraft?.analysisId, plan.createDraft?.selectionPlanId],
  );

  /* Both commands queue durable work and answer `202` with the Operation they queued, so
     both follow it the same way - and neither navigates.

     Queueing used to send the user to the Operation's own screen, which made every action
     a round trip out of the context they were working in and back again. The projection
     carries `active_operation` in full and starts polling the moment it appears, so the
     Application screen reports the work in place. What the accepted `202` still buys is
     the first state: seeding it means the panel appears immediately instead of after the
     next poll, and the Operation screen a direct link reaches is already warm. */
  const followQueued = ({ operation }: QueuedOperation) => {
    queryClient.setQueryData(operationQueryKey(operation.id), operation);
    onQueued(operation.id);
    void queryClient.invalidateQueries({
      queryKey: applicationDetailQueryKey(detail.application.id),
    });
  };

  const analyze = useMutation({
    mutationFn: () => startAnalysis(detail.application.id, snapshotId, analyzeKey, provider),
    onSuccess: followQueued,
  });

  /* §14: the version the two stale-draft commands are addressed to.

     `expected_edit_version` is optimistic concurrency, and it only does that job if it
     comes from a read of the draft itself - the projection carries the draft's id but not
     its version. Conditional, so an Application with nothing to replace opens no second
     request, and shared with the editor's own read through one cache key.

     Read on view rather than on press deliberately: fetching it inside the command would
     make the guard describe the instant of sending rather than what the reader was looking
     at, and a draft edited in another tab would be overwritten instead of refused. */
  const staleDraftId = plan.replaceDraft?.workingDraftId ?? plan.archiveDraft?.workingDraftId ?? null;
  const staleDraftQuery = useQuery({
    ...workingDraftQueryOptions(staleDraftId ?? ""),
    enabled: staleDraftId !== null,
  });
  const editVersion = staleDraftQuery.data?.draft.edit_version ?? null;

  /* The Keep decision is made in the dialog, not assumed by the button. Default on: a
     draft carries manual wording that nothing regenerates, so the reader opts out of
     keeping it rather than having to know to opt in. */
  const [replaceOpen, setReplaceOpen] = useState(false);
  const [keepPrevious, setKeepPrevious] = useState(true);
  /* One key per replaced version: a resent answer for the same version is the same
     command, and a new version is a different one. */
  const replaceKey = useMemo(() => crypto.randomUUID(), [staleDraftId, editVersion]);

  const draft = useMutation({
    mutationFn: async () => {
      /* Availability is the projection's answer, but the IDs are this call's arguments:
         a generate without both of them is not a command this screen may send. */
      if (plan.createDraft === null) {
        throw new Error("create_draft was offered without an active analysis and selection plan");
      }
      return startDraftGeneration(
        detail.application.id,
        plan.createDraft.analysisId,
        plan.createDraft.selectionPlanId,
        draftKey,
        { provider },
      );
    },
    onSuccess: followQueued,
  });

  /* A stale version is the guard doing its job, not a failure to retry: the draft moved
     since this screen read it, so the answer is to show the conflict and re-read, and let
     the reader decide again against what is actually there. `retry: false` on mutations is
     the standing policy (§8.6); this adds the re-read. */
  const onVersionConflict = () => {
    if (staleDraftId !== null) {
      void queryClient.invalidateQueries({ queryKey: workingDraftQueryKey(staleDraftId) });
    }
    void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(detail.application.id) });
  };

  /* Closing restores the default rather than remembering the last answer. The checkbox is
     a per-replacement decision, and an unchecked box carried over from a cancelled dialog
     would make the next replacement silently discard history the reader never chose to
     discard. */
  const closeReplace = () => {
    setReplaceOpen(false);
    setKeepPrevious(true);
  };

  const replace = useMutation({
    mutationFn: async () => {
      /* Availability is the projection's answer, the version is this call's argument, and
         a replacement without either is not a command this screen may send. */
      if (plan.replaceDraft === null || editVersion === null) {
        throw new Error("replace_working_draft was offered without a draft version to address");
      }
      return replaceWorkingDraft(
        detail.application.id,
        {
          expectedEditVersion: editVersion,
          jobAnalysisId: plan.replaceDraft.analysisId,
          keepPrevious,
          selectionPlanId: plan.replaceDraft.selectionPlanId,
          workingDraftId: plan.replaceDraft.workingDraftId,
        },
        replaceKey,
        { provider },
      );
    },
    onError: onVersionConflict,
    onSuccess: (queued) => {
      closeReplace();
      followQueued(queued);
    },
  });

  /* Synchronous, so there is no Operation to follow - only the caches whose answer it
     changed: the draft it archived, and the projection that named it active. */
  const archive = useMutation({
    mutationFn: async () => {
      if (plan.archiveDraft === null || editVersion === null) {
        throw new Error("archive_working_draft was offered without a draft version to address");
      }
      return archiveWorkingDraft(plan.archiveDraft.workingDraftId, editVersion);
    },
    onError: onVersionConflict,
    onSuccess: () => {
      onVersionConflict();
    },
  });

  /* The version read is included: it is what both stale-draft commands are addressed with,
     so a failure to obtain it is the reason the two buttons are disabled and has to be
     said. Silently disabled controls beside an alert about the draft would leave the
     reader with the problem reported and no account of why nothing can act on it. */
  const error =
    settingsQuery.error ?? staleDraftQuery.error ?? analyze.error ?? draft.error ?? replace.error ?? archive.error;

  /* Keyed because the bar renders them from an array: with more than one secondary
     action, React needs each to be identifiable across renders. */
  const analyzeButton =
    plan.analyze === null ? null : (
      <Button
        disabled={settings === undefined}
        key="analyze"
        onClick={() => analyze.mutate()}
        pending={analyze.isPending}
        pendingLabel="מפעיל ניתוח…"
        variant={plan.analyze.emphasized ? "primary" : "secondary"}
      >
        {plan.analyze.reanalysis ? "ניתוח מחדש של המשרה" : "ניתוח המשרה"}
      </Button>
    );

  const draftButton =
    plan.createDraft === null ? null : (
      <Button
        disabled={settings === undefined}
        key="draft"
        onClick={() => draft.mutate()}
        pending={draft.isPending}
        pendingLabel="יוצר טיוטה…"
        variant={plan.createDraft.emphasized ? "primary" : "secondary"}
      >
        יצירת טיוטה
      </Button>
    );

  /* Both wait on the version read: without it neither command can be addressed, and a
     button that answers a press by throwing is worse than one that is plainly not ready
     yet. */
  const replaceButton =
    plan.replaceDraft === null ? null : (
      <Button
        disabled={settings === undefined || editVersion === null}
        key="replace"
        onClick={() => setReplaceOpen(true)}
        pending={replace.isPending}
        pendingLabel="מחליף טיוטה…"
        variant={plan.replaceDraft.emphasized ? "primary" : "secondary"}
      >
        החלפת הטיוטה
      </Button>
    );

  const archiveButton =
    plan.archiveDraft === null ? null : (
      <Button
        disabled={editVersion === null}
        key="archive"
        onClick={() => archive.mutate()}
        pending={archive.isPending}
        pendingLabel="מעביר לארכיון…"
        variant="secondary"
      >
        העברת הטיוטה לארכיון
      </Button>
    );

  const routeButton = (key: string, href: string, label: string, emphasized: boolean) => (
    <Link className={buttonClasses(emphasized ? "primary" : "secondary")} key={key} to={href}>
      {label}
    </Link>
  );
  const draftScreenButton =
    plan.draftScreen === null
      ? null
      : routeButton("draft-screen", plan.draftScreen.href, plan.draftScreen.label, plan.draftScreen.emphasized);
  const readyButton =
    plan.readyRevision === null
      ? null
      : routeButton("ready", plan.readyRevision.href, "צפייה בגרסה המוכנה", plan.readyRevision.emphasized);

  /* Workflow order, and the same order every visit: analyze, draft, the draft screen,
     ready. The bar used to be sorted by how far along each action was, which moved a
     button to the front of the row on the visit it became available - so the control
     under the pointer was not the one that had been there a moment earlier.

     One emphasized primary (A.1), which stays the projection's own `recommended_action`:
     the order below decides position, never emphasis. With nothing recommended, the
     furthest-along offered action leads, because that is the one the workflow is actually
     waiting on. */
  const inWorkflowOrder = [
    { emphasized: plan.analyze?.emphasized === true, node: analyzeButton },
    { emphasized: plan.createDraft?.emphasized === true, node: draftButton },
    { emphasized: plan.replaceDraft?.emphasized === true, node: replaceButton },
    { emphasized: false, node: archiveButton },
    { emphasized: plan.draftScreen?.emphasized === true, node: draftScreenButton },
    { emphasized: plan.readyRevision?.emphasized === true, node: readyButton },
  ].filter((entry): entry is { emphasized: boolean; node: ReactElement } => entry.node !== null);
  const emphasizedEntry =
    inWorkflowOrder.find((entry) => entry.emphasized) ?? inWorkflowOrder[inWorkflowOrder.length - 1];
  const restButtons = inWorkflowOrder.filter((entry) => entry !== emphasizedEntry).map((entry) => entry.node);

  return (
    <div className="flex flex-col gap-4">
      {error === null ? null : (
        <ErrorCallout
          error={error}
          fallbackDetail="לא ניתן להפעיל את הפעולה. מצב המועמדות לא השתנה ואפשר לנסות שוב."
          fallbackTitle="הפעולה לא בוצעה"
        />
      )}

      {plan.unbuiltRecommendation === null ? null : (
        <Callout title={`הפעולה המומלצת כעת היא ${actionLabel(plan.unbuiltRecommendation)}`} tone="neutral">
          {plan.unbuiltRecommendation === "create_draft" && plan.draftWouldReplace
            ? "הטיוטה הפעילה נשמרת כפי שהיא. החלפתה דורשת החלטה מפורשת."
            : "הפעולה אינה זמינה מכאן כרגע."}
        </Callout>
      )}

      {/* Re-analysis destroys nothing: the existing JobAnalysis and any active draft are
          immutable records that stay exactly as they are. What changes is which analysis
          is active, so the consequence is stated rather than confirmed away.

          It is stated where the consequence exists. With no draft to mark stale, the
          sentence was warning about an effect on a record that is not there - one of three
          paragraphs of caveat standing between the reader and the button they came to
          press, and the only one of them attached to the secondary action. */}
      {plan.analyze?.reanalysis === true && plan.draftWouldReplace ? (
        <p className="text-support leading-6 text-cv-text-muted">
          ניתוח מחדש יוצר ניתוח חדש ונפרד לאותו תצלום משרה. הטיוטה הפעילה נשמרת כפי שהיא, אך תסומן כלא מעודכנת מולו.
        </p>
      ) : null}

      {/* The sources are named, not resolved: the draft is built from the analysis and
          the plan the screen is showing, and neither is changed by building from it.

          The clause reassuring the reader that no active draft is being overwritten went
          with the stage that already says so - an offered `create_draft` requires
          `working_draft_state` to be `none`, which is the same fact. It returns above,
          where it stops being true. */}
      {plan.createDraft === null ? null : (
        <p className="text-support leading-6 text-cv-text-muted">
          הטיוטה נוצרת מהניתוח ומתוכנית הבחירה הפעילים של המועמדות. שניהם רשומות שאינן משתנות.
        </p>
      )}

      {/* What pressing it actually costs. The button looks instantaneous and is not: the
          command queues durable work an Operation reports on, and under an AI provider it
          is a paid model call. Which of the two is stated from the same `provider` value
          the command is sent with, so the sentence cannot describe a run different from
          the one the press would start. */}
      {plan.createDraft === null || settings === undefined ? null : (
        <p className="text-support leading-6 text-cv-text-muted">
          {provider === undefined
            ? "היצירה רצה במסלול הדטרמיניסטי, ללא קריאת AI. העבודה מתבצעת ברקע וההתקדמות מדווחת במסך."
            : "היצירה כוללת קריאת AI בתשלום. העבודה מתבצעת ברקע וההתקדמות מדווחת במסך."}
        </p>
      )}

      {/* Why a second analysis is on offer at all. The button sat beside "create draft" at
          equal weight with nothing saying what it is for, and the one sentence that did
          explain it appeared only when there was an active draft to mark stale - so at the
          stage where re-analysis is most freely available it was least explained. */}
      {plan.analyze?.reanalysis === true && !plan.draftWouldReplace ? (
        <p className="text-support leading-6 text-cv-text-muted">
          ניתוח מחדש כדאי רק אם הסיווג שלמעלה נראה שגוי. הוא יוצר ניתוח חדש ונפרד לאותו תצלום משרה, ואינו מושך נוסח משרה
          מעודכן.
        </p>
      ) : null}

      {/* Why the two commands are here at all, and what separates them. They appear only
          beside a stale-draft alert, so the reader has already been told the draft is out
          of date; what they have not been told is that the two buttons are not variants of
          one another. */}
      {plan.replaceDraft === null && plan.archiveDraft === null ? null : (
        <p className="text-support leading-6 text-cv-text-muted">
          הטיוטה אינה מעודכנת מול המקורות שלה. אפשר להחליף אותה בטיוטה חדשה שנבנית מהניתוח ומתוכנית הבחירה הפעילים, או
          להעביר אותה לארכיון — פעולה ששומרת עותק היסטורי ומשאירה את המועמדות בלי טיוטה פעילה.
        </p>
      )}

      {inWorkflowOrder.length === 0 ? null : (
        <ActionBar
          /* The offered actions continue the next-step sentence above them rather than
             closing the page, so they start where that sentence starts. Whether there is
             one of them or several, they are the reader's way on from that line and belong
             beside it, not at the far edge of the card. */
          align="start"
          primary={emphasizedEntry.node}
          secondary={restButtons.length === 0 ? undefined : restButtons}
        />
      )}
      {/* The Keep decision is asked, not assumed, because it is the only choice here whose
          wrong answer cannot be undone: a replacement without it leaves manual wording with
          no historical copy, and nothing regenerates that. Not dismissible for the same
          reason - Escape must not stand for either answer. */}
      <Dialog
        dismissible={false}
        footer={
          <>
            <Button onClick={closeReplace} variant="secondary">
              ביטול
            </Button>
            <Button
              onClick={() => replace.mutate()}
              pending={replace.isPending}
              pendingLabel="מחליף טיוטה…"
              variant="primary"
            >
              החלפת הטיוטה
            </Button>
          </>
        }
        headingId="replace-working-draft-heading"
        onClose={closeReplace}
        open={replaceOpen}
        title="החלפת הטיוטה הפעילה"
      >
        <div className="flex flex-col gap-3">
          <p>
            טיוטה חדשה תיבנה מהניתוח ומתוכנית הבחירה הפעילים. הטיוטה הנוכחית נשמרת כפי שהיא עד שההחלפה מצליחה, ואם היא
            נכשלת — דבר לא משתנה.
          </p>
          <Checkbox
            checked={keepPrevious}
            hint="העותק נשמר כרשומה היסטורית שאינה משתנה. בלעדיו, ניסוח ידני שנעשה בטיוטה הזאת לא יהיה ניתן לשחזור."
            onChange={(event) => setKeepPrevious(event.target.checked)}
          >
            שמירת עותק היסטורי של הטיוטה הנוכחית
          </Checkbox>
        </div>
      </Dialog>
    </div>
  );
};
