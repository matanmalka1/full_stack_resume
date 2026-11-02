import { FileCheck2, type LucideIcon, Pencil, RefreshCw, Settings, Sparkle } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link } from "react-router-dom";

import { aiAvailability } from "@/api/settings";
import type { ApplicationDetail } from "@/api/contracts";
import { routePaths } from "@/navigation/routePaths";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { ListCard, ListRow } from "@/ui/ListCard";
import { PhoneActionBar } from "@/ui/PhoneActionBar";
import { cardClasses } from "@/ui/surface";
import { useWorkflowCommands } from "../../api/mutations";
import { actionLabel } from "../../model/preparationLabels";
import type { WorkflowActionPlan } from "../../model/workflowActionPlan";
import { BuildFromAnalysisDialog } from "./BuildFromAnalysisDialog";
import { PreparationAlerts, hasPreparationAlerts } from "./PreparationAlerts";

/* One thing the step can do, as both places draw it: the recommended card's title, sentence
   and command, or a row of the other actions. */
interface StepAction {
  /* The command itself - a link or a button - for the card. */
  command: ReactNode;
  description?: string;
  icon: LucideIcon;
  key: string;
  label: string;
  /* How the row of other actions reaches it. A row with neither is drawn as inert. */
  onSelect?: () => void;
  to?: string;
}

/* The step that turns the analysis into a draft: the one action the workflow is waiting
   on, in a card of its own; what stands in its way, read-only beside it; and the other
   actions the projection offers, as a list of rows.

   Emphasis is the projection's own `recommended_action`, never the order below. With
   nothing recommended the furthest-along offered action leads, because that is the one
   the workflow is actually waiting on. */
export const NextStepPanel = ({
  detail,
  onQueued,
  operationLive,
  phone,
  plan,
}: {
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
  operationLive: boolean;
  phone: boolean;
  plan: WorkflowActionPlan;
}) => {
  const { analyze, commandsBlocked, draft, error, rebuild, settings, workInFlight } = useWorkflowCommands(
    detail,
    plan,
    onQueued,
    operationLive,
  );
  const [rebuildOpen, setRebuildOpen] = useState(false);
  const closeRebuild = () => setRebuildOpen(false);
  const ai = aiAvailability(settings);
  const aiBlocked = workInFlight || ai !== "available";

  const startRebuild = () => {
    if (plan.buildFromAnalysis?.discardsContent === true) setRebuildOpen(true);
    else rebuild.mutate();
  };

  /* Workflow order, the same on every visit: analyze, rebuild, draft, the editor, ready. */
  const entries: { emphasized: boolean; action: StepAction }[] = [];
  if (plan.analyze !== null && !plan.analyze.reanalysis) {
    entries.push({
      emphasized: plan.analyze.emphasized,
      action: {
        command: (
          <Button
            disabled={aiBlocked}
            onClick={() => analyze.mutate()}
            pending={analyze.isPending}
            pendingLabel="מפעיל ניתוח…"
            size="default"
          >
            ניתוח המשרה
          </Button>
        ),
        description:
          ai === "missing"
            ? "הניתוח דורש ספק AI, ועדיין לא הוגדר כזה."
            : "הניתוח כולל קריאת AI בתשלום, והעבודה מתבצעת ברקע.",
        icon: Sparkle,
        key: "analyze",
        label: "ניתוח המשרה",
        ...(aiBlocked ? {} : { onSelect: () => analyze.mutate() }),
      },
    });
  }
  if (plan.buildFromAnalysis !== null) {
    entries.push({
      emphasized: plan.buildFromAnalysis.emphasized,
      action: {
        command: (
          <Button
            disabled={commandsBlocked}
            onClick={startRebuild}
            pending={rebuild.isPending}
            pendingLabel="בונה מחדש…"
            size="default"
          >
            בנייה מחדש
          </Button>
        ),
        description: plan.buildFromAnalysis.discardsContent
          ? "בנייה מחדש מעבירה את המסמך לניתוח החדש ומוחקת את תוכן הטיוטה הנוכחית."
          : "בנייה מחדש מעבירה את המסמך לניתוח החדש, וממנו תיווצר הטיוטה.",
        icon: RefreshCw,
        key: "rebuild",
        label: "בנייה מחדש מהניתוח החדש",
        ...(commandsBlocked ? {} : { onSelect: startRebuild }),
      },
    });
  }
  if (plan.createDraft !== null) {
    entries.push({
      emphasized: plan.createDraft.emphasized,
      action: {
        command: (
          <Button
            disabled={aiBlocked}
            onClick={() => draft.mutate()}
            pending={draft.isPending}
            pendingLabel="יוצר טיוטה…"
            size="default"
          >
            <Sparkle aria-hidden="true" className="size-icon-md lg:hidden" />
            יצירת טיוטה
          </Button>
        ),
        description:
          ai === "missing"
            ? "יצירת הטיוטה דורשת ספק AI, ועדיין לא הוגדר כזה."
            : "ה־AI בוחר את העובדות, אלא אם כבר בחרת אותן, ומנסח מהן את הטיוטה. היצירה כוללת קריאת AI בתשלום, והעבודה מתבצעת ברקע.",
        icon: Sparkle,
        key: "draft",
        label: "יצירת טיוטה",
        ...(aiBlocked ? {} : { onSelect: () => draft.mutate() }),
      },
    });
  }
  if (plan.draftScreen !== null) {
    const label = plan.draftScreen.action === "approve" ? "מעבר לעורך לבדיקה ואישור" : plan.draftScreen.label;
    entries.push({
      emphasized: plan.draftScreen.emphasized,
      action: {
        command: (
          <Link className={buttonClasses("primary")} to={plan.draftScreen.href}>
            {label}
          </Link>
        ),
        description: "הטיוטה פתוחה בעורך: שם עורכים אותה, בודקים ומאשרים.",
        icon: Pencil,
        key: "draft-screen",
        label,
        to: plan.draftScreen.href,
      },
    });
  }
  if (plan.ready !== null) {
    entries.push({
      emphasized: plan.ready.emphasized,
      action: {
        command: (
          <Link className={buttonClasses("primary")} to={plan.ready.href}>
            צפייה בקורות החיים המוכנים
          </Link>
        ),
        description: "קורות החיים מוכנים למסירה.",
        icon: FileCheck2,
        key: "ready",
        label: "צפייה בקורות החיים המוכנים",
        to: plan.ready.href,
      },
    });
  }

  const lead = entries.find((entry) => entry.emphasized) ?? entries.at(-1);
  const rest = entries.filter((entry) => entry !== lead).map((entry) => entry.action);
  /* An AI step with no provider cannot be pressed, so the card leads with the one thing
     that unblocks it and the inert command stays among the other actions. */
  const providerMissing = ai === "missing" && (lead?.action.key === "draft" || lead?.action.key === "analyze");
  const leadCommand = providerMissing ? (
    <Link className={buttonClasses("primary")} to={routePaths.settings}>
      <Settings aria-hidden="true" className="size-icon-md" />
      פתיחת ההגדרות
    </Link>
  ) : (
    lead?.action.command
  );

  const recommended =
    lead === undefined ? null : (
      <section
        aria-labelledby="next-step-heading"
        className={cardClasses("flex flex-col gap-4 p-7 max-lg:gap-3 max-lg:p-4")}
      >
        <p className="text-support font-bold text-cv-text-muted">
          {detail.recommended_action == null ? "הפעולה הבאה" : "הפעולה המומלצת"}
        </p>
        <div className="flex items-start gap-4 max-lg:gap-3">
          <span
            aria-hidden="true"
            className="flex size-14 shrink-0 items-center justify-center rounded-control-lg bg-cv-accent text-cv-on-accent max-lg:size-11 max-lg:rounded-control"
          >
            <lead.action.icon className="size-6 max-lg:size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-heading-md font-extrabold text-cv-text max-lg:text-heading-card" id="next-step-heading">
              {lead.action.label}
            </h2>
            {lead.action.description === undefined ? null : (
              <p className="mt-1.5 text-body leading-relaxed text-cv-text-muted max-lg:text-label">
                {lead.action.description}
              </p>
            )}
          </div>
        </div>
        {phone ? null : <div className="flex *:shadow-action">{leadCommand}</div>}
      </section>
    );

  const others =
    rest.length === 0 ? null : (
      <section aria-labelledby="other-actions-heading" className="flex flex-col gap-2 lg:gap-0">
        <h2 className="px-1 text-support font-bold text-cv-text-muted lg:sr-only" id="other-actions-heading">
          פעולות זמינות
        </h2>
        <ListCard>
          {!phone ? (
            <li aria-hidden="true" className="px-4 pt-4 pb-1 text-support font-bold text-cv-text-muted">
              פעולות זמינות
            </li>
          ) : null}
          {rest.map((action) => (
            <ListRow
              icon={phone ? action.icon : undefined}
              key={action.key}
              label={action.label}
              {...(action.to === undefined ? {} : { to: action.to })}
              {...(action.onSelect === undefined ? {} : { onClick: action.onSelect })}
            />
          ))}
        </ListCard>
      </section>
    );

  const alerts = hasPreparationAlerts(detail) ? <PreparationAlerts compact detail={detail} /> : null;
  const notices = (
    <>
      {error === null ? null : (
        <ErrorCallout error={error} fallbackDetail="מצב המועמדות לא השתנה. אפשר לנסות שוב." title="הפעולה לא הופעלה" />
      )}
      {plan.unbuiltRecommendation === null ? null : (
        <Callout title={`הפעולה המומלצת כעת היא ${actionLabel(plan.unbuiltRecommendation)}`} tone="neutral">
          אין לה כרגע מסך שמבצע אותה, ולכן אין לאן להפנות. הפעולות שכן מוצעות כאן הן הדרך להמשיך.
        </Callout>
      )}
    </>
  );

  return (
    <>
      {phone ? (
        <div className="flex flex-col gap-3.5">
          {notices}
          {recommended}
          {alerts}
          {others}
        </div>
      ) : (
        <div className="flex items-start gap-5">
          <div className="flex min-w-0 flex-1 flex-col gap-4">
            {notices}
            {recommended}
          </div>
          {alerts === null && others === null ? null : (
            <aside aria-label="התראות ופעולות נוספות" className="flex w-80 shrink-0 flex-col gap-3.5">
              {alerts}
              {others}
            </aside>
          )}
        </div>
      )}

      {phone && leadCommand !== undefined ? <PhoneActionBar>{leadCommand}</PhoneActionBar> : null}

      <BuildFromAnalysisDialog
        commandsBlocked={commandsBlocked}
        onClose={closeRebuild}
        onConfirm={() => rebuild.mutate(undefined, { onSuccess: closeRebuild })}
        open={rebuildOpen}
        pending={rebuild.isPending}
      />
    </>
  );
};
