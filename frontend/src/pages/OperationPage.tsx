import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiProblem } from "../api/client";
import type { Operation, OperationPhase, OperationStatus } from "../api/contracts";
import { isTerminalOperation, operationQueryOptions } from "../api/operations";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { LiveRegion } from "../ui/LiveRegion";
import { LtrText } from "../ui/LtrText";
import { PageHeading } from "../ui/PageHeading";
import { StatusBadge } from "../ui/StatusBadge";
import { type StatusTone } from "../ui/status";
import { SummaryList, type SummaryItem } from "../ui/SummaryList";
import { TechnicalDetails } from "../ui/TechnicalDetails";
import { OperationActions } from "./OperationActions";

/* Keyed by the generated unions, so a status or phase added to the backend lifecycle
   fails the frontend build instead of reaching the screen untranslated. */
const statusLabels: Record<OperationStatus, string> = {
  queued: "ממתינה בתור",
  running: "מתבצעת",
  succeeded: "הושלמה",
  failed: "נכשלה",
  cancelled: "בוטלה",
  interrupted: "נקטעה",
};

const statusTones: Record<OperationStatus, StatusTone> = {
  queued: "progress",
  running: "progress",
  succeeded: "success",
  failed: "blocker",
  cancelled: "neutral",
  interrupted: "warning",
};

const phaseLabels: Record<OperationPhase, string> = {
  queued: "ממתינה בתור",
  waiting_for_application: "ממתינה למועמדות",
  waiting_for_render_slot: "ממתינה לתור הרינדור",
  waiting_for_ai_slot: "ממתינה לתור המודל",
  pre_execution_check: "בדיקה לפני ביצוע",
  executing: "בביצוע",
  retry_wait: "המתנה לפני ניסיון חוזר",
  pre_activation_check: "בדיקה לפני הפעלת התוצר",
  activating: "מפעילה את התוצר",
  completed: "הושלמה",
};

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
    { term: "נוצרה", value: operation.created_at, ltr: true },
  ];

  if (operation.failure_code != null) {
    items.push({ term: "קוד הכשל", value: operation.failure_code, ltr: true });
  }
  if (operation.retry_of_operation_id != null) {
    items.push({ term: "ניסיון חוזר של", value: operation.retry_of_operation_id, ltr: true });
  }

  return items;
};

const failureTones: Partial<Record<OperationStatus, StatusTone>> = {
  failed: "blocker",
  cancelled: "neutral",
  interrupted: "warning",
};

/* A.5: the live region announces a status or phase change, never a polling tick. The
   dependencies are the two values themselves, so an identical tick re-renders without
   re-running the effect. */
const usePhaseAnnouncement = (
  status: OperationStatus | undefined,
  phase: OperationPhase | undefined,
): string => {
  const [announcement, setAnnouncement] = useState("");
  const lastAnnounced = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (status === undefined || phase === undefined) {
      return;
    }

    const spoken = `${statusLabels[status]}. ${phaseLabels[phase]}.`;

    if (lastAnnounced.current !== spoken) {
      lastAnnounced.current = spoken;
      setAnnouncement(spoken);
    }
  }, [phase, status]);

  return announcement;
};

export const OperationPage = () => {
  const { operationId } = useParams();

  /* The route is operations/:operationId, so a missing id is a router invariant
     violation rather than a state this screen supports. */
  if (operationId === undefined) {
    throw new Error("OperationPage rendered without an operationId route parameter");
  }

  const query = useQuery(operationQueryOptions(operationId));
  const operation = query.data;
  const announcement = usePhaseAnnouncement(operation?.status, operation?.phase);
  const terminal = isTerminalOperation(operation);

  return (
    <Card aria-labelledby="route-heading">
      <PageHeading
        description={
          terminal
            ? "הפעולה הסתיימה והעדכון האוטומטי נעצר."
            : "העמוד מתעדכן מעצמו עד לסיום הפעולה."
        }
        id="route-heading"
      >
        {operation === undefined ? "מצב הפעולה" : statusLabels[operation.status]}
      </PageHeading>

      <LiveRegion>{announcement}</LiveRegion>

      {query.error === null ? null : (
        <Callout
          className="mt-6"
          role="alert"
          title={
            query.error instanceof ApiProblem
              ? query.error.problem.title
              : "לא ניתן לטעון את מצב הפעולה"
          }
          tone="blocker"
        >
          {query.error instanceof ApiProblem
            ? query.error.problem.detail
            : "הפנייה לשרת נכשלה. אם הפעולה עדיין רצה, העמוד ימשיך לנסות."}
          {query.error instanceof ApiProblem ? (
            <TechnicalDetails className="mt-3">
              <LtrText>{query.error.problem.code}</LtrText>
            </TechnicalDetails>
          ) : null}
        </Callout>
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
            <span className="text-body text-cv-text-muted">{phaseLabels[operation.phase]}</span>
          </div>

          {/* A.3: the safe progress line comes from the backend and is English today, so
              it picks its own direction rather than inheriting the RTL shell. */}
          {operation.message === "" ? null : (
            <p className="text-body leading-7" dir="auto">
              {operation.message}
            </p>
          )}

          {operation.safe_failure_detail == null ? null : (
            <Callout
              role="alert"
              title={statusLabels[operation.status]}
              tone={failureTones[operation.status] ?? "warning"}
            >
              {operation.safe_failure_detail}
            </Callout>
          )}

          <SummaryList items={progressItems(operation)} />

          <TechnicalDetails>
            <SummaryList items={technicalItems(operation)} />
          </TechnicalDetails>

          <OperationActions operation={operation} />
        </div>
      )}
    </Card>
  );
};
