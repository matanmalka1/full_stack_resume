import { type ReactElement } from "react";
import { Link } from "react-router-dom";

import type { ApplicationDetail } from "../../api/contracts";
import { ErrorCallout } from "../../app/ErrorCallout";
import { ActionBar } from "../../ui/ActionBar";
import { Button, buttonClasses } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { ReplaceDraftDialog } from "./ReplaceDraftDialog";
import { actionLabel } from "./applicationLabels";
import { useApplicationActionsMutations } from "./useApplicationActionsMutations";

interface ApplicationActionsProps {
  detail: ApplicationDetail;
  /* What this component just queued. The projection reports an Operation only on its next
     read, so without this the panel would appear a poll later than the press that caused
     it - and a command that failed before the worker picked it up might never be reported
     at all. The accepted `202` is the earliest and most certain answer, so it is handed
     straight to the screen that shows it. */
  onQueued: (operationId: string) => void;
}

export const ApplicationActions = ({ detail, onQueued }: ApplicationActionsProps) => {
  const {
    analyze,
    archive,
    closeReplace,
    commandsBlocked,
    draft,
    editVersion,
    error,
    keepPrevious,
    plan,
    provider,
    replace,
    replaceOpen,
    setKeepPrevious,
    setReplaceOpen,
    settings,
    workInFlight,
  } = useApplicationActionsMutations(detail, onQueued);

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
        disabled={settings === undefined || editVersion === null || commandsBlocked}
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
        disabled={editVersion === null || commandsBlocked}
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
      : routeButton(
          "draft-screen",
          plan.draftScreen.href,
          plan.draftScreen.label === "אישור הגרסה" ? "מעבר לעורך לאימות ואישור" : plan.draftScreen.label,
          plan.draftScreen.emphasized,
        );
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
            : "אין לה כרגע מסך שמבצע אותה, ולכן אין לאן להפנות. הפעולות שכן מוצעות למטה הן הדרך להמשיך מכאן."}
        </Callout>
      )}

      {/* One line above the bar, and only about the action the bar leads with.

          What stood here was up to three stacked paragraphs of caveat between the reader
          and the button they came to press. Every sentence in them is still on the screen;
          what changed is that only the cost of the offered command is stated before the
          control, and the explanations of the secondary actions moved below it - they
          answer "why is that other button here", which is a question asked after the row
          is seen, not before.

          The generate note names its sources and its cost in one sentence. Which cost is
          read from the same `provider` value the command is sent with, so the sentence
          cannot describe a run different from the one the press would start. */}
      {plan.createDraft === null || settings === undefined ? null : (
        <p className="text-support leading-6 text-cv-text-muted">
          הטיוטה נוצרת מהניתוח ומתוכנית הבחירה הפעילים — שתי רשומות שאינן משתנות.{" "}
          {provider === undefined
            ? "היצירה רצה במסלול הדטרמיניסטי, ללא קריאת AI, והעבודה מתבצעת ברקע."
            : "היצירה כוללת קריאת AI בתשלום, והעבודה מתבצעת ברקע."}
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

      {/* Why the secondary actions are on offer at all, below the row that offers them.

          Re-analysis destroys nothing: the existing JobAnalysis and any active draft are
          immutable records that stay exactly as they are. What changes is which analysis
          is active - stated, not confirmed away, and stated differently depending on
          whether there is a draft for it to mark stale. */}
      {plan.analyze?.reanalysis !== true ? null : (
        <p className="text-support leading-6 text-cv-text-muted">
          {plan.draftWouldReplace
            ? "ניתוח מחדש יוצר ניתוח חדש ונפרד לאותו תצלום משרה. הטיוטה הפעילה נשמרת כפי שהיא, אך תסומן כלא מעודכנת מולו."
            : "ניתוח מחדש כדאי רק אם הסיווג שלמעלה נראה שגוי. הוא יוצר ניתוח חדש ונפרד לאותו תצלום משרה, ואינו מושך נוסח משרה מעודכן."}
        </p>
      )}

      {/* What separates the two stale-draft commands. They appear only beside a stale-draft
          alert, so the reader has already been told the draft is out of date; what they
          have not been told is that the two buttons are not variants of one another. */}
      {plan.replaceDraft === null && plan.archiveDraft === null ? null : (
        <p className="text-support leading-6 text-cv-text-muted">
          החלפה בונה טיוטה חדשה מהניתוח ומתוכנית הבחירה הפעילים. העברה לארכיון שומרת עותק היסטורי ומשאירה את המועמדות
          בלי טיוטה פעילה.
        </p>
      )}

      {/* Why the controls are inert rather than missing. A button that vanishes while work
          runs reads as a command that is no longer offered; one that is disabled with the
          reason beside it reads as the same command, later. */}
      {workInFlight && (plan.replaceDraft !== null || plan.archiveDraft !== null) ? (
        <p className="text-support leading-6 text-cv-text-muted">
          פעולה על הטיוטה מתבצעת כעת. החלפה והעברה לארכיון יהיו זמינות שוב כשהיא תסתיים.
        </p>
      ) : null}

      <ReplaceDraftDialog
        commandsBlocked={commandsBlocked}
        keepPrevious={keepPrevious}
        onClose={closeReplace}
        onKeepPreviousChange={setKeepPrevious}
        open={replaceOpen}
        replace={replace}
      />
    </div>
  );
};
