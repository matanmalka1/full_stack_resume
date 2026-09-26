import { ChevronLeft, X } from "lucide-react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";

import type { Operation } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";
import { aiRegenerationAvailable } from "@/api/settings";
import { useSettings } from "@/api/useSettings";
import { cx } from "@/ui/cx";
import { Dialog } from "@/ui/Dialog";
import { LiveRegion } from "@/ui/LiveRegion";
import { StatusBadge } from "@/ui/StatusBadge";
import { StatusSlot } from "@/ui/StatusSlot";
import { type Tone, tonePresentation } from "@/ui/tone";
import { operationTypeLabels, statusLabels, statusTones } from "../model/operationLabels";
import { isOperationStarting } from "../model/operationLive";
import { operationProgressLabel } from "../model/operationProgress";
import { OperationPhaseSteps } from "./OperationPhaseSteps";
import { OperationReport } from "./OperationReport";

export interface PendingWork {
  heading: ReactNode;
  note: ReactNode;
}

const PENDING_LABEL = "נשלחה לביצוע";

const chipToneClasses: Record<Tone, string> = {
  success: "border-cv-success/30 text-cv-success",
  warning: "border-cv-warning/30 text-cv-warning",
  blocker: "border-cv-blocker/30 text-cv-blocker",
  info: "border-cv-info/30 text-cv-info",
  progress: "border-cv-accent/30 text-cv-accent",
  neutral: "border-cv-border text-cv-text-muted",
};

interface Session {
  /* A run this screen watched starting is still in progress, or is finishing: it
     succeeded and the views it changed are still being read again. */
  active: boolean;
  /* The full report is open. It opens by itself only on an outcome that needs the
     reader - a failure, a cancellation, an interruption - and otherwise on request. */
  dialogOpen: boolean;
  /* A finished record already on hand when the session started - history, such as the
     last run before a command that then failed to queue. It is not this session's
     outcome, so ending on it does not hold anything open over an old failure. */
  historyId: string | null;
  /* The reader put the live panel away; the status row at the top of the step stands in
     for it until the run ends. */
  panelHidden: boolean;
  /* The run whose success the panel is still showing, briefly, before it goes. */
  succeededId: string | null;
}

const SUCCESS_LINGER_MS = 3_000;

/* Work in progress, beside the screen that queued it rather than over it.

   Live work shows in a small panel at the top corner of the viewport. It does not dim
   or block the page: the screen already locks the actions that conflict with the run by
   `isOperationLive`, whether or not anything is showing, so a modal over the page guarded
   nothing and hid what the reader was waiting on. The panel fades in only after a short
   delay, so a run that finishes in a fraction of a second never flashes a frame, and a
   success stays a moment and goes - it leaves no permanent row behind.

   An outcome that needs the reader - a failure, a cancellation, an interruption - opens
   the full report as a dialog, because that is where a decision is asked for. Such an
   outcome also leaves a status row in the step's one status slot, which reopens it. So
   does live work whose panel the reader put away.

   One instance per screen, and one session per stretch of work rather than per record.
   Pending work, the record that replaces it, a retry's new record, and a run the screen
   continues straight into (an analysis followed by its draft) are all the same wait for
   the reader, so none of them ends the session or remounts anything. A run that was
   already finished when the screen read it is history: it never pops over a reload.

   The dialog is always mounted, closed or not. The report inside owns the delayed reveal
   of cancel, and a reopened run must not wait for it again. */
export const OperationOverlay = ({
  awaitingRecord,
  continuation,
  failureAction,
  inline = false,
  onQueued,
  operation,
  pending,
  settled,
}: {
  awaitingRecord: boolean;
  /* What happens next by itself, when this run succeeding is not the end of the work. */
  continuation?: string | undefined;
  /* Host-owned recovery for the record this Operation failed to produce. */
  failureAction?: ReactNode;
  /* The live panel sits in the page flow instead of floating at the viewport's corner,
     and cannot be put away. For a host with nothing else to show while the run lasts -
     the analysis step before its first analysis - where a corner panel over an empty
     page said less than the page itself could. */
  inline?: boolean;
  /* A retry from inside the report belongs to the same watch the host screen keeps. */
  onQueued: (operationId: string) => void;
  operation: Operation | undefined;
  /* Work this screen asked for before any Operation record exists to report it. */
  pending?: PendingWork | undefined;
  settled: boolean;
}) => {
  const headingId = useId();
  const panelHeadingId = useId();
  const chipRef = useRef<HTMLButtonElement>(null);
  const { settings } = useSettings();
  const [session, setSession] = useState<Session>({
    active: false,
    dialogOpen: false,
    historyId: null,
    panelHidden: false,
    succeededId: null,
  });

  const starting = isOperationStarting({
    awaitingRecord,
    continuation,
    operation,
    pending: pending !== undefined,
    settled,
  });
  const succeeded = operation?.status === "succeeded";
  const live = starting || (session.active && succeeded && !settled);

  /* Adjusted during render, from values this render already holds, so the panel is on
     screen in the same paint that shows the work - never a frame after it. */
  if (starting && !session.active) {
    setSession({
      active: true,
      dialogOpen: false,
      historyId: operation !== undefined && isTerminalOperation(operation) ? operation.id : null,
      panelHidden: false,
      succeededId: null,
    });
  } else if (session.active && !live) {
    const outcome = operation !== undefined && operation.id !== session.historyId ? operation : undefined;
    setSession({
      active: false,
      dialogOpen: outcome !== undefined && outcome.status !== "succeeded",
      historyId: null,
      panelHidden: false,
      succeededId: outcome?.status === "succeeded" ? outcome.id : null,
    });
  }

  /* Putting the panel away removes the button that did it. The status row takes the
     panel's place, so focus goes there instead of falling back to the page. */
  useEffect(() => {
    if (session.panelHidden) chipRef.current?.focus();
  }, [session.panelHidden]);

  useEffect(() => {
    if (session.succeededId === null) return;
    const timeout = window.setTimeout(
      () => setSession((current) => ({ ...current, succeededId: null })),
      SUCCESS_LINGER_MS,
    );
    return () => window.clearTimeout(timeout);
  }, [session.succeededId]);

  /* While new work is asked for or its record is on its way, the record on hand is the
     previous run's: its outcome is not this run's, so the report waits for the new one. */
  const record = awaitingRecord || pending !== undefined ? undefined : operation;
  if (record === undefined && pending === undefined && !awaitingRecord) return null;

  const typeLabel = operation === undefined ? null : operationTypeLabels[operation.operation_type];
  const heading = pending?.heading ?? (typeLabel === null ? "הרצה" : <>הרצת {typeLabel}</>);
  const continuing = continuation !== undefined;
  /* A refused AI run is history once a provider is available again: it no longer blocks
     anything, and a fresh run may succeed. The row stops drawing it as an open blocker
     and says what can be done, instead of staying red until the next run replaces it. */
  const retryableRefusal =
    record?.status === "failed" &&
    (record.failure_code === "PROVIDER_REFUSED" || record.failure_code === "PROVIDER_NOT_CONFIGURED") &&
    settings !== undefined &&
    aiRegenerationAvailable(settings);
  const tone: Tone =
    record === undefined || continuing ? "progress" : retryableRefusal ? "warning" : statusTones[record.status];
  const statusText =
    record === undefined
      ? PENDING_LABEL
      : continuing
        ? "ממשיכה לשלב הבא"
        : isTerminalOperation(record)
          ? retryableRefusal
            ? `${statusLabels[record.status]} · אפשר לנסות שוב`
            : statusLabels[record.status]
          : operationProgressLabel(record);
  /* A.5: the live region is mounted for as long as there is anything to report, so it is
     the one place the run's progress is announced from. The same single sentence the
     status shows, so an identical poll tick re-renders without speaking. */
  const announcement = record === undefined ? (pending?.note ?? PENDING_LABEL) : (continuation ?? statusText);
  const Icon = tonePresentation[tone].icon;

  const showingSuccess = !session.active && session.succeededId !== null && session.succeededId === record?.id;
  const showPanel = (session.active && !session.panelHidden) || showingSuccess;
  /* The row in the step's status slot: an outcome that needs the reader, or live work
     whose panel was put away. A success leaves nothing behind - the page shows its
     result - and neither does a success the screen found on arrival. */
  const showChip =
    (session.active && session.panelHidden) ||
    (!session.active && record !== undefined && isTerminalOperation(record) && record.status !== "succeeded");
  const openDialog = () => setSession((current) => ({ ...current, dialogOpen: true }));

  return (
    <>
      {showChip ? (
        <StatusSlot>
          <button
            aria-haspopup="dialog"
            className={cx(
              "cv-settle-in flex w-full items-center gap-3 rounded-surface border bg-cv-surface px-4 py-2.5 text-start text-support shadow-surface transition-colors hover:bg-cv-surface-muted",
              chipToneClasses[tone],
            )}
            onClick={openDialog}
            ref={chipRef}
            type="button"
          >
            <Icon aria-hidden="true" className={cx("size-icon-md shrink-0", tone === "progress" && "animate-spin")} />
            <span className="min-w-0 flex-1 text-cv-text">
              <span className="font-semibold">{heading}</span>
              <span className="text-cv-text-muted"> · {statusText}</span>
            </span>
            <span className="flex shrink-0 items-center gap-1 font-medium underline underline-offset-4">
              פירוט ההרצה
              <ChevronLeft aria-hidden="true" className="size-icon-sm" />
            </span>
          </button>
        </StatusSlot>
      ) : null}

      {showPanel ? (
        <section
          aria-labelledby={panelHeadingId}
          className={cx(
            "cv-appear-late flex flex-col gap-2.5 rounded-surface border bg-cv-surface p-4",
            inline
              ? "shadow-surface"
              : "fixed inset-x-4 top-[4.5rem] z-(--cv-z-toast) shadow-floating lg:inset-x-auto lg:end-6 lg:top-6 lg:w-[22rem]",
            chipToneClasses[tone],
          )}
        >
          <div className="flex items-start gap-2.5">
            <Icon
              aria-hidden="true"
              className={cx("mt-0.5 size-icon-md shrink-0", tone === "progress" && "animate-spin")}
            />
            <div className="min-w-0 flex-1 text-support">
              <h2 className="font-semibold text-cv-text" id={panelHeadingId}>
                {heading}
              </h2>
              <p className="text-cv-text-muted">{statusText}</p>
            </div>
            {showingSuccess || inline ? null : (
              <button
                aria-label="סגירה"
                className="-m-1 rounded-control p-1 text-cv-text-muted hover:bg-cv-surface-muted hover:text-cv-text"
                onClick={() => setSession((current) => ({ ...current, panelHidden: true }))}
                type="button"
              >
                <X aria-hidden="true" className="size-icon-md" />
              </button>
            )}
          </div>
          {showingSuccess ? null : record === undefined || continuing ? (
            <p className="text-support leading-6 text-cv-text-muted" dir="auto">
              {continuation ?? pending?.note ?? "ההרצה נשלחה. המצב שלה יופיע כאן מיד."}
            </p>
          ) : (
            <>
              <OperationPhaseSteps phase={record.phase} />
              {/* In place of the page's own content, the card says what fills it. */}
              {inline ? (
                <p className="text-support leading-6 text-cv-text-muted">
                  התוצאה תופיע כאן כשההרצה תסתיים. אפשר לעזוב את המסך בינתיים.
                </p>
              ) : null}
            </>
          )}
          {showingSuccess ? null : (
            <button
              aria-haspopup="dialog"
              className="w-fit text-support font-medium text-cv-text underline underline-offset-4"
              onClick={openDialog}
              type="button"
            >
              פירוט ההרצה
            </button>
          )}
        </section>
      ) : null}

      <LiveRegion>{announcement}</LiveRegion>

      <Dialog
        headingId={headingId}
        onClose={() => setSession((current) => ({ ...current, dialogOpen: false }))}
        open={session.dialogOpen}
        restoreFocusTo={chipRef}
        title={heading}
      >
        {record === undefined ? (
          <div className="flex flex-col gap-4">
            <div>
              <StatusBadge tone="progress">{PENDING_LABEL}</StatusBadge>
            </div>
            <p className="text-support leading-6 text-cv-text-muted" dir="auto">
              {pending?.note ?? "ההרצה נשלחה. המצב שלה יופיע כאן מיד."}
            </p>
          </div>
        ) : (
          <OperationReport
            continuation={continuation}
            failureAction={failureAction}
            onQueued={onQueued}
            operation={record}
          />
        )}
      </Dialog>
    </>
  );
};
