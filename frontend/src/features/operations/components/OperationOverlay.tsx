import { ChevronLeft } from "lucide-react";
import { type ReactNode, useId, useRef, useState } from "react";

import type { Operation } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";
import { cx } from "@/ui/cx";
import { Dialog } from "@/ui/Dialog";
import { LiveRegion } from "@/ui/LiveRegion";
import { StatusBadge } from "@/ui/StatusBadge";
import { type Tone, tonePresentation } from "@/ui/tone";
import { operationTypeLabels, statusLabels, statusTones } from "../model/operationLabels";
import { isOperationStarting } from "../model/operationLive";
import { operationProgressLabel } from "../model/operationProgress";
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
  /* A finished record already on hand when the session started - history, such as the
     last run before a command that then failed to queue. It is not this session's
     outcome, so ending on it does not hold the overlay open over an old failure. */
  historyId: string | null;
  open: boolean;
}

/* Work in progress, over the screen that queued it.

   It used to be a panel in the page flow: a card that pushed the step below it down while
   the run lasted and then stayed as a row reporting that finished work had finished. Work
   in flight now sits over the page instead, and what is left once it is over is a chip in
   the place the card was - the run's status in one line, which reopens its full report.

   One instance per screen, and one session per stretch of work rather than per record.
   Pending work, the record that replaces it, a retry's new record, and a run the screen
   continues straight into (an analysis followed by its draft) are all the same wait for
   the reader, so none of them closes the overlay or remounts it. Only the start of work
   this screen watched opens it by itself: a run that was already finished when the screen
   read it is history, reachable from the chip, and never pops over a reload.

   The session ends when nothing is starting and a success's refresh has landed. A success
   closes by itself, so the reader looks at the page its result is on; anything else
   stays open - the failure, its guidance and the retry are the most important thing on
   the screen then - and opens again if the reader had hidden it.

   Hiding the overlay never unmounts the report. The report owns the delayed reveal of
   cancel, and a reopened run must not wait for it again. Nor does hiding it make the page
   safe to edit: screens lock the actions that conflict with a run by `isOperationLive`,
   whether or not the overlay is showing. */
export const OperationOverlay = ({
  awaitingRecord,
  continuation,
  failureAction,
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
  /* A retry from inside the report belongs to the same watch the host screen keeps. */
  onQueued: (operationId: string) => void;
  operation: Operation | undefined;
  /* Work this screen asked for before any Operation record exists to report it. */
  pending?: PendingWork | undefined;
  settled: boolean;
}) => {
  const headingId = useId();
  const chipRef = useRef<HTMLButtonElement>(null);
  const [session, setSession] = useState<Session>({ active: false, historyId: null, open: false });

  const starting = isOperationStarting({
    awaitingRecord,
    continuation,
    operation,
    pending: pending !== undefined,
    settled,
  });
  const succeeded = operation?.status === "succeeded";
  const live = starting || (session.active && succeeded && !settled);

  /* Adjusted during render, from values this render already holds, so the overlay is
     open in the same paint that shows the work - never a frame after it. */
  if (starting && !session.active) {
    setSession({
      active: true,
      historyId: operation !== undefined && isTerminalOperation(operation) ? operation.id : null,
      open: true,
    });
  } else if (session.active && !live) {
    setSession({
      active: false,
      historyId: null,
      open: operation !== undefined && operation.id !== session.historyId && !succeeded,
    });
  }

  /* While new work is asked for or its record is on its way, the record on hand is the
     previous run's: its outcome is not this run's, so the report waits for the new one. */
  const record = awaitingRecord || pending !== undefined ? undefined : operation;
  if (record === undefined && pending === undefined && !awaitingRecord) return null;

  const typeLabel = operation === undefined ? null : operationTypeLabels[operation.operation_type];
  const heading = pending?.heading ?? (typeLabel === null ? "הרצה" : <>הרצת {typeLabel}</>);
  const continuing = continuation !== undefined;
  const tone: Tone = record === undefined || continuing ? "progress" : statusTones[record.status];
  const statusText =
    record === undefined
      ? PENDING_LABEL
      : continuing
        ? "ממשיכה לשלב הבא"
        : isTerminalOperation(record)
          ? statusLabels[record.status]
          : operationProgressLabel(record);
  /* A.5: the chip is mounted for as long as there is anything to report, hidden overlay
     or not, so it is the one place the run's progress is announced from. The same single
     sentence the badge shows, so an identical poll tick re-renders without speaking. */
  const announcement = record === undefined ? (pending?.note ?? PENDING_LABEL) : (continuation ?? statusText);
  const Icon = tonePresentation[tone].icon;

  return (
    <>
      <button
        aria-haspopup="dialog"
        className={cx(
          "cv-settle-in flex w-full items-center gap-3 rounded-surface border bg-cv-surface px-4 py-2.5 text-start text-support shadow-surface transition-colors hover:bg-cv-surface-muted",
          chipToneClasses[tone],
        )}
        onClick={() => setSession((current) => ({ ...current, open: true }))}
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
      <LiveRegion>{announcement}</LiveRegion>

      <Dialog
        headingId={headingId}
        onClose={() => setSession((current) => ({ ...current, open: false }))}
        open={session.open}
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
