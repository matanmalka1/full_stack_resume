import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { applicationDetailQueryOptions, startDraftGeneration } from "../api/applications";
import { ApiProblem } from "../api/client";
import type {
  Operation,
  OperationFailureCode,
  OperationPhase,
  OperationStatus,
  OperationType,
} from "../api/contracts";
import { isTerminalOperation, operationQueryOptions } from "../api/operations";
import { operationQueryKey } from "../api/operations";
import { settingsQueryOptions } from "../api/settings";
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
import { autoDraftSources } from "./autoDraft";

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

/* What the operation is, which the status alone never says. Keyed by the generated
   union, so a new backend operation type fails the build rather than reaching the
   heading untranslated. */
const operationTypeLabels: Record<OperationType, string> = {
  analyze_job: "ניתוח המשרה",
  propose_selection_plan: "בחירת העובדות",
  create_draft: "יצירת הטיוטה",
  regenerate_section: "יצירה מחדש של פרק",
  regenerate_claim: "יצירה מחדש של טענה",
  render_revision: "יצירת קובץ קורות החיים",
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

interface FailurePresentation {
  title: string;
  guidance: string;
}

const providerRetryGuidance =
  "לא בוצע מעבר אוטומטי למצב דטרמיניסטי. אפשר ליצור ניסיון חדש, או לחזור למועמדות ולבחור באפשרות המשך אחרת כאשר השרת מציע אותה.";
const providerOutputGuidance =
  "התשובה לא הופעלה ולא הוחלפה בשקט בתוצאה דטרמיניסטית. אפשר ליצור ניסיון חדש, או לחזור למועמדות ולבחור באפשרות המשך אחרת כאשר השרת מציע אותה.";

/* Failure codes are decisions a person must be able to distinguish, not technical
   decoration. This map is exhaustive over the generated union: adding a backend code
   fails the build until the screen says what it means and what remains safe. The
   backend-authored safe detail is still shown verbatim; this copy explains the next
   choice without exposing logs, paths, or provider text. */
const failurePresentations: Record<OperationFailureCode, FailurePresentation> = {
  SOURCE_CHANGED: {
    title: "המקור השתנה בזמן הפעולה",
    guidance:
      "התוצאה לא הופעלה והמצב הקיים נשמר. ניסיון חוזר משתמש שוב במקורות שהוקפאו לפעולה הזו ועלול להיכשל מאותה סיבה; חזרה למועמדות מציגה את הפעולות שמותר לבצע מול המקור העדכני.",
  },
  PROVIDER_TIMEOUT: {
    title: "ספק הבינה המלאכותית לא השיב בזמן",
    guidance: providerRetryGuidance,
  },
  PROVIDER_RATE_LIMITED: {
    title: "ספק הבינה המלאכותית הגביל את הבקשה",
    guidance: providerRetryGuidance,
  },
  PROVIDER_UNAVAILABLE: {
    title: "ספק הבינה המלאכותית אינו זמין",
    guidance: providerRetryGuidance,
  },
  PROVIDER_REFUSED: {
    title: "ספק הבינה המלאכותית סירב לבקשה",
    guidance: providerRetryGuidance,
  },
  INVALID_OUTPUT: {
    title: "הצעת הספק לא הייתה בטוחה לשימוש",
    guidance: providerOutputGuidance,
  },
  SCHEMA_VIOLATION: {
    title: "תשובת הספק לא הייתה במבנה הנדרש",
    guidance: providerOutputGuidance,
  },
  RENDER_FAILED: {
    title: "יצירת קובץ קורות החיים נכשלה",
    guidance: "הגרסה שאושרה נשמרה. אפשר ליצור ניסיון חדש בלי לשנות אותה.",
  },
  BROWSER_START_FAILED: {
    title: "מנוע יצירת הקובץ לא התחיל",
    guidance: "הגרסה שאושרה נשמרה. אפשר ליצור ניסיון חדש בלי לשנות אותה.",
  },
  VALIDATION_EXECUTION_FAILED: {
    title: "לא ניתן להשלים את בדיקות הפעולה",
    guidance: "המצב שהיה פעיל לפני הפעולה נשמר. אפשר ליצור ניסיון חדש או לחזור למועמדות.",
  },
  CANCELLED_BEFORE_ACTIVATION: {
    title: "הפעולה בוטלה לפני הפעלת התוצאה",
    guidance: "תוצאה שהושלמה לאחר בקשת הביטול נשמרת כראיה לא פעילה ואינה מחליפה את המצב הקיים.",
  },
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

const autoDraftInFlight = new Set<string>();

const autoDraftStorageKey = (operationId: string): string => `stage-e:auto-draft:${operationId}`;

export const OperationPage = () => {
  const { operationId } = useParams();

  /* The route is operations/:operationId, so a missing id is a router invariant
     violation rather than a state this screen supports. */
  if (operationId === undefined) {
    throw new Error("OperationPage rendered without an operationId route parameter");
  }

  const query = useQuery(operationQueryOptions(operationId));
  const operation = query.data;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const analyzeSucceeded = operation?.operation_type === "analyze_job" && operation.status === "succeeded";
  const settingsQuery = useQuery({ ...settingsQueryOptions, enabled: analyzeSucceeded });
  const applicationQuery = useQuery({
    ...applicationDetailQueryOptions(operation?.application_id ?? ""),
    enabled: analyzeSucceeded,
  });
  const autoDraft = useMutation({
    mutationFn: async ({ applicationId, analysisId, planId }: { applicationId: string; analysisId: string; planId: string }) =>
      startDraftGeneration(
        applicationId,
        analysisId,
        planId,
        `auto-draft:${operationId}:${analysisId}:${planId}`,
      ),
    onSuccess: ({ operation: queued, operationPath }) => {
      sessionStorage.setItem(autoDraftStorageKey(operationId), "accepted");
      autoDraftInFlight.delete(operationId);
      queryClient.setQueryData(operationQueryKey(queued.id), queued);
      void navigate(operationPath);
    },
    onError: () => autoDraftInFlight.delete(operationId),
  });

  useEffect(() => {
    const sources = autoDraftSources(
      operation,
      settingsQuery.data?.settings,
      applicationQuery.data,
      sessionStorage.getItem(autoDraftStorageKey(operationId)) === "accepted",
      autoDraftInFlight.has(operationId),
    );
    if (sources === null) return;
    autoDraftInFlight.add(operationId);
    autoDraft.mutate(sources);
  }, [applicationQuery.data, operation, operationId, settingsQuery.data]);
  const announcement = usePhaseAnnouncement(
    operation?.status,
    operation?.phase,
    operation?.cancellation_requested_at,
  );
  const terminal = isTerminalOperation(operation);
  const failure =
    operation?.failure_code == null ? null : failurePresentations[operation.failure_code];

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
        {/* The heading names the work; the badge below carries its status. Printing the
            status here too made a finished operation say the same word twice before the
            reader learned which operation it was. */}
        {operation === undefined
          ? "מצב הפעולה"
          : operationTypeLabels[operation.operation_type]}
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
            {/* Phase is the progress axis and only says something the status badge has
                not already said while work is still moving. At a terminal status the two
                collapse onto the same word — `succeeded` and `completed` are both
                "הושלמה" — so the phase is dropped rather than printed twice. */}
            {terminal ? null : (
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

          <SummaryList items={progressItems(operation)} />

          <TechnicalDetails>
            <SummaryList items={technicalItems(operation)} />
          </TechnicalDetails>

          <OperationActions operation={operation} />
          {autoDraft.error === null ? null : (
            <Callout role="alert" title="הטיוטה האוטומטית לא הופעלה" tone="blocker">
              {autoDraft.error instanceof ApiProblem
                ? autoDraft.error.problem.detail
                : "אפשר לחזור למועמדות ולהפעיל יצירת טיוטה ידנית."}
            </Callout>
          )}
        </div>
      )}
    </Card>
  );
};
