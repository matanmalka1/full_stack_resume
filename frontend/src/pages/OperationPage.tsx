import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { applicationDetailQueryOptions } from "../api/applications";
import type { Operation, OperationPhase, OperationStatus } from "../api/contracts";
import { isTerminalOperation, operationQueryOptions } from "../api/operations";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { LiveRegion } from "../ui/LiveRegion";
import { LtrText } from "../ui/LtrText";
import { PageHeading } from "../ui/PageHeading";
import { StatusBadge } from "../ui/StatusBadge";
import { SummaryList, type SummaryItem } from "../ui/SummaryList";
import { OperationActions } from "./OperationActions";
import { actionDestination } from "./actionDestinations";
import { actionLabel, preparationStateNextStep } from "./applicationLabels";
import {
  activeOutputLabels,
  failurePresentations,
  failureTones,
  joinHebrewList,
  operationTypeLabels,
  phaseLabels,
  statusLabels,
  statusTones,
} from "./operationLabels";

const dateTimeFormat = new Intl.DateTimeFormat("he-IL", {
  dateStyle: "short",
  timeStyle: "medium",
});

/* The raw ISO timestamp stays available under the technical details; an unparsable
   value is shown as it arrived rather than as "Invalid Date". */
const formatDateTime = (value: string): string => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : dateTimeFormat.format(parsed);
};

const progressItems = (operation: Operation): SummaryItem[] => {
  const items: SummaryItem[] = [{ term: "נוצרה", value: formatDateTime(operation.created_at) }];

  if (operation.started_at != null) {
    items.push({ term: "התחילה", value: formatDateTime(operation.started_at) });
  }
  if (operation.finished_at != null) {
    items.push({ term: "הסתיימה", value: formatDateTime(operation.finished_at) });
  }
  if (operation.cancellation_requested_at != null) {
    items.push({
      term: "התבקש ביטול",
      value: formatDateTime(operation.cancellation_requested_at),
    });
  }

  return items;
};

const technicalItems = (operation: Operation): SummaryItem[] => {
  const items: SummaryItem[] = [
    { term: "מזהה הפעולה", value: operation.id, ltr: true },
    { term: "מזהה המועמדות", value: operation.application_id, ltr: true },
    { term: "סוג הפעולה", value: operation.operation_type, ltr: true },
    { term: "חותמת הזמן המקורית", value: operation.created_at, ltr: true },
  ];

  if (operation.failure_code != null) {
    items.push({ term: "קוד הכשל", value: operation.failure_code, ltr: true });
  }
  if (operation.retry_of_operation_id != null) {
    items.push({ term: "ניסיון חוזר של", value: operation.retry_of_operation_id, ltr: true });
  }

  return items;
};

/* A.5: the live region announces a status, phase, or cancellation-request change, never
   a polling tick. The dependencies are those values themselves, so an identical tick
   re-renders without re-running the effect. */
const usePhaseAnnouncement = (
  status: OperationStatus | undefined,
  phase: OperationPhase | undefined,
  cancellationRequestedAt: string | null | undefined,
): string => {
  const [announcement, setAnnouncement] = useState("");
  const lastAnnounced = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (status === undefined || phase === undefined) {
      return;
    }

    const cancellation =
      cancellationRequestedAt == null ? "" : " בקשת הביטול התקבלה.";
    /* Status and phase are two axes that share vocabulary at their ends: `succeeded`
       and `completed` are both "הושלמה". Announcing both verbatim makes a listener
       hear one word twice and learn nothing from the repeat, so the phase is spoken
       only when it differs from the status. */
    const statusText = statusLabels[status];
    const phaseText = phaseLabels[phase];
    const spoken =
      phaseText === statusText
        ? `${statusText}.${cancellation}`
        : `${statusText}. ${phaseText}.${cancellation}`;

    if (lastAnnounced.current !== spoken) {
      lastAnnounced.current = spoken;
      setAnnouncement(spoken);
    }
  }, [cancellationRequestedAt, phase, status]);

  return announcement;
};

/* The automatic draft continuation is not here.

   It lives on the Application screen, which is where the flow now stays: queueing work no
   longer navigates, so this route is reached by a direct link or a reload rather than in
   the ordinary course of the workflow. Running the chain in both places would let one
   analyze Operation queue two drafts - the storage key guards a reload of the same screen,
   not two screens watching the same Operation at once. */
export const OperationPage = () => {
  const { operationId } = useParams();

  /* The route is operations/:operationId, so a missing id is a router invariant
     violation rather than a state this screen supports. */
  if (operationId === undefined) {
    throw new Error("OperationPage rendered without an operationId route parameter");
  }

  const query = useQuery(operationQueryOptions(operationId));
  const operation = query.data;
  /* Enabled for any operation, not only a succeeded analyze: the projection is what
     lets a running Operation publish the stage it belongs to, so the landmark keeps
     showing the workflow position instead of dropping back to the intake step for as
     long as the operation is on screen. */
  const applicationQuery = useQuery({
    ...applicationDetailQueryOptions(operation?.application_id ?? ""),
    enabled: operation !== undefined,
  });
  useWorkflowStage(
    applicationQuery.data === undefined ? "unknown" : applicationQuery.data.preparation_state,
  );
  const announcement = usePhaseAnnouncement(
    operation?.status,
    operation?.phase,
    operation?.cancellation_requested_at,
  );
  const terminal = isTerminalOperation(operation);
  const failure =
    operation?.failure_code == null ? null : failurePresentations[operation.failure_code];
  const succeeded = operation?.status === "succeeded";
  const produced = operation === undefined ? [] : activeOutputLabels(operation);

  /* While work is moving, the description is about the page: it refreshes itself. Once
     the work is over that sentence is spent, and "the automatic refresh has stopped" is a
     fact about polling machinery offered to someone who wants to know what happened. So a
     finished operation describes its outcome instead, and a successful one names what it
     produced when the outputs say.

     What comes next is the projection's answer, not this screen's: the sentence is the
     same `preparationStateNextStep` the Application screen shows, read from the same
     projection, so this reports the workflow position rather than deciding one (A.1). The
     detail query polls while an Operation is live and stops at a terminal status, so by
     the time this renders the stage it names is the post-operation stage.

     Pointing at the other screen instead - "go back and it will tell you" - was the same
     deferral the finished Operation used to make with its buttons, on a screen that
     already holds the answer. */
  /* The lookup is guarded rather than indexed straight: `preparation_state` is a union
     the backend owns, and a projection carrying a stage this build does not know would
     otherwise stringify `undefined` into the sentence. Missing copy falls back to the
     deferral, which is always true. */
  const nextStep = applicationQuery.data
    ? (preparationStateNextStep[applicationQuery.data.preparation_state] ?? null)
    : null;
  
  const recommended = applicationQuery.data?.recommended_action ?? null;
  const recommendedHref =
    recommended === null || operation === undefined
      ? null
      : actionDestination(recommended, operation.application_id);

  const completion =
    produced.length === 0 ? "הפעולה הושלמה." : `הפעולה הושלמה ויצרה ${joinHebrewList(produced)}.`;
  const description = !terminal
    ? "העמוד מתעדכן מעצמו עד לסיום הפעולה."
    : succeeded
      ? nextStep === null
        ? `${completion} חזרה למועמדות מציגה מה הפעולה הבאה.`
        : `${completion} ${nextStep}`
      : "הפעולה הסתיימה והעדכון האוטומטי נעצר.";

  return (
    <Card aria-labelledby="route-heading">
      <PageHeading
        description={description}
        eyebrow={terminal ? "פעולה שהסתיימה" : "פעולה מתבצעת"}
        id="route-heading"
      >
        {/* The heading names the work; the badge below carries its status. Printing the
            status here too made a finished operation say the same word twice before the
            reader learned which operation it was. */}
        {operation === undefined
          ? "מצב הפעולה"
          : operationTypeLabels[operation.operation_type]}
      </PageHeading>

      <LiveRegion>{announcement}</LiveRegion>

      {query.error === null ? null : (
        <ErrorCallout
          className="mt-6"
          error={query.error}
          fallbackDetail="הפנייה לשרת נכשלה. אם הפעולה עדיין רצה, העמוד ימשיך לנסות."
          fallbackTitle="לא ניתן לטעון את מצב הפעולה"
        />
      )}

      {operation === undefined ? (
        query.error === null ? (
          <p className="mt-6 text-body text-cv-text-muted">טוען את מצב הפעולה…</p>
        ) : null
      ) : (
        <div className="mt-6 flex flex-col gap-6">
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge tone={statusTones[operation.status]}>
              {statusLabels[operation.status]}
            </StatusBadge>
            {/* Phase is the progress axis and earns its place only when it says
                something the status badge has not. The two share vocabulary at both ends
                — `queued`/`queued` are both "ממתינה בתור", `succeeded`/`completed` both
                "הושלמה" — so the test is whether the words differ, not whether the run
                has finished. Keyed on `terminal` alone, a queued run said one word
                twice. */}
            {phaseLabels[operation.phase] === statusLabels[operation.status] ? null : (
              <span className="text-body text-cv-text-muted">{phaseLabels[operation.phase]}</span>
            )}
          </div>

          {/* A.3: the safe progress line comes from the backend and is English today, so
              it picks its own direction rather than inheriting the RTL shell. */}
          {operation.message === "" ? null : (
            <p className="text-body leading-7" dir="auto">
              {operation.message}
            </p>
          )}

          {failure === null && operation.safe_failure_detail == null ? null : (
            <Callout
              role="alert"
              title={failure?.title ?? statusLabels[operation.status]}
              tone={failureTones[operation.status] ?? "warning"}
            >
              {operation.safe_failure_detail == null ? null : (
                <p dir="auto">{operation.safe_failure_detail}</p>
              )}
              {failure === null ? null : (
                <p className="mt-2" dir="auto">
                  {failure.guidance}
                </p>
              )}
            </Callout>
          )}

          {operation.cancellation_requested_at != null && !operation.is_terminal ? (
            <Callout title="בקשת הביטול התקבלה" tone="neutral">
              הביטול של פעולה שכבר התחילה הוא מיטבי. גם אם העבודה החיצונית תסתיים,
              התוצאה שלה לא תופעל; העמוד ימשיך להתעדכן עד שיירשם המצב הסופי.
            </Callout>
          ) : null}

          {operation.status === "cancelled" && failure === null ? (
            <Callout title="הפעולה בוטלה" tone="neutral">
              לא הופעלה תוצאה חדשה והמצב שהיה פעיל לפני הפעולה נשמר.
            </Callout>
          ) : null}

          {/* Open, not collapsed. Everywhere else the record is a footnote to a screen
              doing other work, and stays behind a disclosure. This route exists to lay
              the record out - it is what the panel's "פרטי הפעולה המלאים" link promises -
              so hiding it here left the screen with nothing but a restatement of the
              summary the reader already had. Two lists of different kinds, each named. */}
          <div className="flex flex-col gap-5 rounded-surface border border-cv-border bg-cv-surface-muted p-5">
            <div>
              <h2 className="mb-2 text-support font-semibold text-cv-text">מהלך הפעולה</h2>
              <SummaryList items={progressItems(operation)} />
            </div>
            <div>
              <h2 className="mb-2 text-support font-semibold text-cv-text">מזהי הרשומה</h2>
              <SummaryList items={technicalItems(operation)} />
            </div>
          </div>

          <OperationActions
            operation={operation}
            returnLabel={
              recommendedHref === null || recommended === null
                ? undefined
                : actionLabel(recommended)
            }
            returnPath={recommendedHref ?? undefined}
          />
        </div>
      )}
    </Card>
  );
};
