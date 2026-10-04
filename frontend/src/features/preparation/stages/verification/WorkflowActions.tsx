import { type ReactElement, useId, useState } from "react";
import { Link } from "react-router-dom";

import { aiAvailability } from "@/api/settings";
import { routePaths } from "@/navigation/routePaths";
import type { ApplicationDetail } from "@/api/contracts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { CommitBar, NEXT_STEP_LABEL } from "@/ui/CommitBar";
import { useWorkflowCommands } from "../../api/mutations";
import { actionLabel } from "../../model/preparationLabels";
import type { WorkflowActionPlan } from "../../model/workflowActionPlan";
import { BuildFromAnalysisDialog } from "./BuildFromAnalysisDialog";

interface WorkflowActionsProps {
  detail: ApplicationDetail;
  /* Whether the projection names one specific action rather than merely permitting
     several. Only the notes region's name depends on it. */
  hasRecommendation: boolean;
  /* What this component just queued. The projection reports an Operation only on its next
     read, so without this the overlay would appear a poll later than the press that caused
     it - and a command that failed before the worker picked it up might never be reported
     at all. The accepted `202` is the earliest and most certain answer, so it is handed
     straight to the screen that shows it. */
  onQueued: (operationId: string) => void;
  /* Whether this Application's work is under way, by `isOperationLive`. It holds the
     commands whether or not the run's overlay is showing: hiding the overlay does not make
     it safe to queue work over the run the page is waiting on. */
  operationLive: boolean;
  /* Read once by the view that owns this screen and handed down, so the plan every
     control on the screen is drawn from is literally the same object. */
  plan: WorkflowActionPlan;
}

export const WorkflowActions = ({ detail, hasRecommendation, onQueued, operationLive, plan }: WorkflowActionsProps) => {
  const { analyze, commandsBlocked, draft, error, rebuild, settings, workInFlight } = useWorkflowCommands(
    detail,
    plan,
    onQueued,
    operationLive,
  );

  /* The rebuild asks first only when it would discard written content; with no content
     there is nothing to lose, and the press is the decision. */
  const [rebuildOpen, setRebuildOpen] = useState(false);
  const analyzeReasonId = useId();
  const closeRebuild = () => setRebuildOpen(false);

  /* Keyed because the bar renders them from an array: with more than one secondary
     action, React needs each to be identifiable across renders.

     Re-analysis is not offered here. Once an analysis is already in force this button
     would sit beside "יצירת טיוטה" - the actual next step - competing with it for a press
     that is rarely the one worth making; `ReanalyzeCard` offers the same command instead
     where the analysis it re-runs is on screen, in the diagnostics tab. The first analyze
     of an Application that has none stays exactly here: there is no analysis yet for a
     diagnostics tab to show. */
  /* A first analysis or a generate with no provider cannot be pressed, so the bar leads
     with the one thing that unblocks it. The inert button stays beside it, secondary, so
     the step still names its action. */
  const ai = aiAvailability(settings);
  const aiMissing = ai === "missing";
  const offersAiStep = (plan.analyze !== null && !plan.analyze.reanalysis) || plan.createDraft !== null;
  const providerMissing = aiMissing && offersAiStep;
  const analyzeButton =
    plan.analyze === null || plan.analyze.reanalysis ? null : (
      <Button
        aria-describedby={providerMissing ? analyzeReasonId : undefined}
        disabled={workInFlight || ai !== "available"}
        key="analyze"
        onClick={() => analyze.mutate()}
        pending={analyze.isPending}
        pendingLabel="מפעיל ניתוח…"
        variant={plan.analyze.emphasized && !providerMissing ? "primary" : "secondary"}
      >
        ניתוח המשרה
      </Button>
    );
  /* Links in the bar take the compact size `Button` defaults to, so a link and a button
     side by side in it are one height. */
  const settingsButton = providerMissing ? (
    <Link className={buttonClasses("primary", undefined, "compact")} key="settings" to={routePaths.settings}>
      פתיחת ההגדרות
    </Link>
  ) : null;

  const draftButton =
    plan.createDraft === null ? null : (
      <Button
        aria-describedby={providerMissing ? analyzeReasonId : undefined}
        disabled={workInFlight || ai !== "available"}
        key="draft"
        onClick={() => draft.mutate()}
        pending={draft.isPending}
        pendingLabel="יוצר טיוטה…"
        variant={plan.createDraft.emphasized && !providerMissing ? "primary" : "secondary"}
      >
        יצירת טיוטה
      </Button>
    );

  const rebuildButton =
    plan.buildFromAnalysis === null ? null : (
      <Button
        disabled={commandsBlocked}
        key="rebuild"
        onClick={() => {
          if (plan.buildFromAnalysis?.discardsContent === true) setRebuildOpen(true);
          else rebuild.mutate();
        }}
        pending={rebuild.isPending}
        pendingLabel="בונה מחדש…"
        variant={plan.buildFromAnalysis.emphasized ? "primary" : "secondary"}
      >
        בנייה מחדש מהניתוח החדש
      </Button>
    );

  const routeButton = (key: string, href: string, label: string, emphasized: boolean) => (
    <Link className={buttonClasses(emphasized ? "primary" : "secondary", undefined, "compact")} key={key} to={href}>
      {label}
    </Link>
  );
  const draftScreenButton =
    plan.draftScreen === null
      ? null
      : routeButton(
          "draft-screen",
          plan.draftScreen.href,
          plan.draftScreen.action === "approve" ? "מעבר לעורך לבדיקה ואישור" : plan.draftScreen.label,
          /* The projection's own recommendation, not a constant. A generate queued here
             advances to the editor by itself, so this link is what a reader who
             deliberately returned to analysis presses - and when the workflow is waiting
             on a check or approval, it is the action they came back for. */
          plan.draftScreen.emphasized,
        );
  const readyButton =
    plan.ready === null
      ? null
      : routeButton("ready", plan.ready.href, "צפייה בקורות החיים המוכנים", plan.ready.emphasized);

  /* A first analysis says in the bar what pressing it costs, or why it cannot be
     pressed: an inert button with no reason beside it reads as a broken one. The way to
     fix a missing provider is the bar's own lead action. */
  const analyzeNote =
    plan.analyze === null || plan.analyze.reanalysis || ai === "loading" ? undefined : (
      <p className="text-support leading-6 text-cv-text-muted" id={analyzeReasonId}>
        {ai === "available"
          ? "הניתוח כולל קריאת AI בתשלום, והעבודה מתבצעת ברקע."
          : "הניתוח דורש ספק AI, ועדיין לא הוגדר כזה."}
      </p>
    );
  /* The generate note names its sources and its cost in one sentence, in the bar beside
     the button it describes, or why it cannot be pressed. */
  const draftNote =
    plan.createDraft === null || ai === "loading" ? undefined : (
      <p className="text-support leading-6 text-cv-text-muted" id={analyzeReasonId}>
        {aiMissing
          ? "יצירת הטיוטה דורשת ספק AI, ועדיין לא הוגדר כזה."
          : "ה־AI בוחר את העובדות, אלא אם כבר בחרת אותן, ומנסח מהן את הטיוטה. היצירה כוללת קריאת AI בתשלום, והעבודה מתבצעת ברקע."}
      </p>
    );

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
    { emphasized: plan.buildFromAnalysis?.emphasized === true, node: rebuildButton },
    { emphasized: plan.createDraft?.emphasized === true, node: draftButton },
    { emphasized: plan.draftScreen?.emphasized === true, node: draftScreenButton },
    { emphasized: plan.ready?.emphasized === true, node: readyButton },
    { emphasized: true, node: settingsButton },
  ].filter((entry): entry is { emphasized: boolean; node: ReactElement } => entry.node !== null);
  const emphasizedEntry =
    inWorkflowOrder.find((entry) => entry.emphasized) ?? inWorkflowOrder[inWorkflowOrder.length - 1];
  const restButtons = inWorkflowOrder.filter((entry) => entry !== emphasizedEntry).map((entry) => entry.node);

  /* Whether this component draws anything that stays on the step. Its commit bar is
     portalled to the shell's action slot and its replacement dialog is closed, so on a
     step whose plan offers only a route - "צפייה בגרסה המוכנה" on a finished Application -
     everything below renders somewhere else or not at all. The named region used to wrap
     that outcome anyway, leaving a labelled landmark of zero height that a screen reader
     announced and then had nothing to read out of. It now wraps the notes themselves and
     exists only when there are notes. */
  const hasNotes = error !== null || plan.unbuiltRecommendation !== null || plan.buildFromAnalysis !== null;

  return (
    <div className="flex flex-col gap-4">
      {!hasNotes ? null : (
        <section aria-label={hasRecommendation ? "הפעולה המומלצת" : "פעולות זמינות"} className="flex flex-col gap-4">
          {error === null ? null : (
            <ErrorCallout
              error={error}
              fallbackDetail="מצב המועמדות לא השתנה. אפשר לנסות שוב."
              title="הפעולה לא הופעלה"
            />
          )}

          {plan.unbuiltRecommendation === null ? null : (
            <Callout title={`הפעולה המומלצת כעת היא ${actionLabel(plan.unbuiltRecommendation)}`} tone="neutral">
              אין לה כרגע מסך שמבצע אותה, ולכן אין לאן להפנות. הפעולות שכן מוצעות למטה הן הדרך להמשיך מכאן.
            </Callout>
          )}

          {/* What the rebuild does, beside the button that does it: it is the one action
          here whose effect is not obvious from its name. */}
          {plan.buildFromAnalysis === null ? null : (
            <p className="text-support leading-6 text-cv-text-muted">
              {plan.buildFromAnalysis.discardsContent
                ? "בנייה מחדש מעבירה את המסמך לניתוח החדש ומוחקת את תוכן הטיוטה הנוכחית."
                : "בנייה מחדש מעבירה את המסמך לניתוח החדש, וממנו תיווצר הטיוטה."}
            </p>
          )}
        </section>
      )}

      {/* The step's action, in the one place every step puts it, and last so the bar it
          pins to the viewport has nothing of this region left underneath it. It used to
          sit mid-flow, which meant the reader found it in a different position on each of
          the three screens - and on a long preparation screen, only after scrolling past
          the alerts and the diagnosis. The sentences above it are what is said before the
          press; the bar is the press. */}
      {inWorkflowOrder.length === 0 ? null : (
        <CommitBar
          label={NEXT_STEP_LABEL}
          primary={
            <>
              {restButtons.length === 0 ? null : <div className="flex flex-wrap gap-3">{restButtons}</div>}
              {emphasizedEntry.node}
            </>
          }
        >
          {/* The two notes never meet: a first analysis offers no draft yet. */}
          {analyzeNote ?? draftNote}
        </CommitBar>
      )}

      <BuildFromAnalysisDialog
        commandsBlocked={commandsBlocked}
        onClose={closeRebuild}
        onConfirm={() => rebuild.mutate(undefined, { onSuccess: closeRebuild })}
        open={rebuildOpen}
        pending={rebuild.isPending}
      />
    </div>
  );
};
