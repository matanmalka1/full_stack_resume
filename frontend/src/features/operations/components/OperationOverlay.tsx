import { ChevronLeft, Info, Sparkles, TriangleAlert, X } from "lucide-react";
import { type ReactNode, useEffect, useId, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

import type { Operation } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";
import { useAiAvailability } from "@/features/settings";
import { cx } from "@/ui/cx";
import { Dialog } from "@/ui/Dialog";
import { IconButton } from "@/ui/IconButton";
import { LiveRegion } from "@/ui/LiveRegion";
import { StatusBadge } from "@/ui/StatusBadge";
import { StatusSlot } from "@/ui/StatusSlot";
import { type Tone, toneBorderClasses, tonePresentation, toneTextClasses } from "@/ui/tone";
import {
  operationTypeLabels,
  pageFitLabel,
  pageFitNotice,
  phaseLabels,
  statusLabels,
  statusTones,
  withheldLabel,
} from "../model/operationLabels";
import { useIsPhone } from "../hooks/useIsPhone";
import { failureSummary } from "../model/failureSummary";
import { durationLabel } from "../model/operationElapsed";
import { isOperationStarting } from "../model/operationLive";
import { operationProgressLabel } from "../model/operationProgress";
import { OperationFailurePage } from "./OperationFailurePage";
import { OperationPhaseSteps } from "./OperationPhaseSteps";
import { OperationReport } from "./OperationReport";
import { OperationRunActions, OperationRunBar } from "./OperationRunBar";

export interface PendingWork {
  heading: ReactNode;
  note: ReactNode;
}

const PENDING_LABEL = "נשלחה לביצוע";

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

/* Proposed lines a succeeded run withheld. Its result stands, but those lines kept their
   wording from before the run, so it is an outcome that needs the reader like a failure:
   one that goes by itself would let a line stay unchanged without anyone seeing why. */
const withheldCount = (operation: Operation): number =>
  operation.status === "succeeded" ? (operation.withheld_claims?.claims.length ?? 0) : 0;

/* A succeeded draft that was trimmed to its page limit, is still over it, or could not be
   measured: the document is not quite what the run's success alone would suggest, so the
   reader is shown why, as for withheld lines. */
const needsReader = (operation: Operation): boolean =>
  isTerminalOperation(operation) &&
  (operation.status !== "succeeded" || withheldCount(operation) > 0 || pageFitNotice(operation) !== null);

/* Work in progress, beside the screen that queued it rather than over it.

   Live work shows in a small panel at the top corner of the viewport. It does not dim
   or block the page: the screen already locks the actions that conflict with the run by
   `isOperationLive`, whether or not anything is showing, so a modal over the page guarded
   nothing and hid what the reader was waiting on. The panel fades in only after a short
   delay, so a run that finishes in a fraction of a second never flashes a frame, and a
   success stays a moment and goes - it leaves no permanent row behind.

   An outcome that needs the reader - a failure, a cancellation, an interruption, a success
   that withheld some of its proposed lines - opens
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
  eyebrow,
  failureAction,
  inline = false,
  inlineNote = "התוצאה תופיע כאן כשההרצה תסתיים. אפשר לעזוב את המסך בינתיים.",
  onQueued,
  operation,
  pending,
  runActions = false,
  settled,
}: {
  awaitingRecord: boolean;
  /* What happens next by itself, when this run succeeding is not the end of the work. */
  continuation?: string | undefined;
  /* Whose work this is - role and company - over the inline run, where the run is the
     step's whole body: on a phone the page's own heading is out of view, and on a wide
     screen the run is a card of its own that names the work it is for. */
  eyebrow?: ReactNode;
  /* Host-owned recovery for the record this Operation failed to produce. */
  failureAction?: ReactNode;
  /* The live panel sits in the page flow instead of floating at the viewport's corner,
     and cannot be put away. For a host with nothing else to show while the run lasts -
     the analysis step before its first analysis - where a corner panel over an empty
     page said less than the page itself could.

     Inline is also how a host that already shows the run in its own body reports it
     exactly once: the corner panel is not drawn while the page holds the same run. It
     changes only where live work is shown - a failure still opens the report and leaves
     a status row, and a success still shows before it goes - and a host on another
     screen, which does not show the run inline, keeps the corner panel. */
  inline?: boolean;
  /* What the inline panel says fills its place once the run ends. A host that shows its
     own run inline because it would otherwise report it twice - the editor, whose render
     used to have a banner of its own beside the corner panel - names where the reader
     goes next instead. */
  inlineNote?: ReactNode;
  /* A retry from inside the report belongs to the same watch the host screen keeps. */
  onQueued: (operationId: string) => void;
  operation: Operation | undefined;
  /* Work this screen asked for before any Operation record exists to report it. */
  pending?: PendingWork | undefined;
  /* An inline run closes on its own two ways on - back to the board, or cancel: a bar of
     its own on a phone, the foot of the centred card on a wide screen. Only for a host
     whose step has no bar of its own while the run is its body. */
  runActions?: boolean;
  settled: boolean;
}) => {
  const headingId = useId();
  const panelHeadingId = useId();
  const chipRef = useRef<HTMLButtonElement>(null);
  const [navigating, setNavigating] = useState(false);
  const location = useLocation();
  const [shownAtLocation, setShownAtLocation] = useState(location.key);
  const ai = useAiAvailability();
  const isPhone = useIsPhone();
  const [now, setNow] = useState(() => Date.now());
  const [session, setSession] = useState<Session>({
    active: false,
    dialogOpen: false,
    historyId: null,
    panelHidden: false,
    succeededId: null,
  });
  // The editor settles buffered edits before navigating and captures the click,
  // so the Link's own onClick may never run. The location is the reliable signal
  // that navigation was accepted. Release the native modal before claim focus.
  if (shownAtLocation !== location.key) {
    setShownAtLocation(location.key);
    setNavigating(true);
    setSession((current) => ({ ...current, dialogOpen: false }));
  }

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
      dialogOpen: outcome !== undefined && needsReader(outcome),
      historyId: null,
      panelHidden: false,
      succeededId: outcome?.status === "succeeded" && !needsReader(outcome) ? outcome.id : null,
    });
  }

  /* The inline run says how long it has been executing, so its clock ticks while it
     lives. The record is polled on its own schedule; a second's tick is the clock's. */
  const ticking = inline && live;
  useEffect(() => {
    if (!ticking) return undefined;
    const interval = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(interval);
  }, [ticking]);

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
  /* A run that had no provider is history once one is available: it no longer blocks
     anything, and a fresh run may succeed. The row stops drawing it as an open blocker
     and says what can be done, instead of staying red until the next run replaces it. */
  const retryableRefusal =
    record?.status === "failed" && record.failure_code === "PROVIDER_NOT_CONFIGURED" && ai === "available";
  const withheld = record === undefined ? 0 : withheldCount(record);
  const pageFit = record === undefined ? null : pageFitNotice(record);
  /* What a succeeded run left for the reader to look at, in the status row's few words. */
  const succeededNotes = [
    ...(withheld > 0 ? [withheldLabel(withheld)] : []),
    ...(pageFit === null ? [] : [pageFitLabel(pageFit)]),
  ];
  const tone: Tone =
    record === undefined || continuing
      ? "progress"
      : retryableRefusal || withheld > 0 || pageFit?.status === "trimmed" || pageFit?.status === "over"
        ? "warning"
        : pageFit?.status === "unavailable"
          ? "info"
          : statusTones[record.status];
  const statusText =
    record === undefined
      ? PENDING_LABEL
      : continuing
        ? "ממשיכה לשלב הבא"
        : isTerminalOperation(record)
          ? retryableRefusal
            ? `${statusLabels[record.status]} · אפשר לנסות שוב`
            : succeededNotes.length > 0
              ? [statusLabels[record.status], ...succeededNotes].join(" · ")
              : statusLabels[record.status]
          : operationProgressLabel(record);
  /* A.5: the live region is mounted for as long as there is anything to report, so it is
     the one place the run's progress is announced from. The same single sentence the
     status shows, so an identical poll tick re-renders without speaking. */
  const announcement = record === undefined ? (pending?.note ?? PENDING_LABEL) : (continuation ?? statusText);
  const Icon = tonePresentation[tone].icon;
  const elapsed =
    record?.started_at == null || isTerminalOperation(record) ? null : durationLabel(record.started_at, now);
  const activeNote =
    !inline || record === undefined || elapsed === null
      ? undefined
      : `${phaseLabels[record.phase]} · זמן שחלף: ${elapsed}`;
  /* A run that ended without a result is a page of its own (see `OperationFailurePage`):
     a phone's sheet, and on a wide screen the same page as a centred card. It once was
     the phone's alone, the wide dialog reading the failure as a callout over the full
     report; the desktop design draws it the phone's way, so both widths now say it once,
     in one tree. A failed review keeps the full report: its own panel lists the lines
     and the facts behind them, which the page has no room for. */
  const failurePage =
    record !== undefined &&
    isTerminalOperation(record) &&
    record.status !== "succeeded" &&
    record.failure_reason?.code !== "claim_review";
  const failure = failurePage ? failureSummary(record, ai === "available", ai !== "loading") : null;

  const showingSuccess = !session.active && session.succeededId !== null && session.succeededId === record?.id;
  const showPanel = (session.active && !session.panelHidden) || showingSuccess;
  /* The row in the step's status slot: an outcome that needs the reader, or live work
     whose panel was put away. A plain success leaves nothing behind - the page shows its
     result - and neither does one the screen found on arrival. */
  const showChip =
    (session.active && session.panelHidden) || (!session.active && record !== undefined && needsReader(record));
  /* The run is the step's whole body and closes on its own ways on: on a wide screen it
     is then the centred card of the design - who it is for, the ring, the run named large,
     its steps in a row of their own, the note and the two ways on - rather than a card
     at the top of an otherwise empty step. Inline runs on other hosts (the editor) sit
     beside content of their own and keep the plain card there. */
  const card = inline && runActions;
  const openDialog = () => {
    setNavigating(false);
    setSession((current) => ({ ...current, dialogOpen: true }));
  };

  return (
    <>
      {showChip ? (
        <StatusSlot>
          <button
            aria-haspopup="dialog"
            className={cx(
              "cv-settle-in flex w-full items-center gap-3 rounded-surface border bg-cv-surface px-4 py-2.5 text-start text-support shadow-surface transition-colors hover:bg-cv-surface-muted",
              toneBorderClasses[tone],
              toneTextClasses[tone],
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
            "flex flex-col gap-2.5 rounded-surface border bg-cv-surface p-4",
            /* Inline, the panel is the step's body, not a notice over it: held back like
               the corner panel, it left the space under the heading empty for the delay
               and then dropped a card into it. It settles in at once instead. */
            inline ? "cv-settle-in" : "cv-appear-late",
            inline
              ? /* On a phone the inline run is the step's whole screen, not a card on it:
                   the frame falls away, the run is named large under a turning ring, and
                   only its steps keep a card of their own. */
                cx(
                  "shadow-surface max-lg:gap-4 max-lg:border-0 max-lg:bg-transparent max-lg:p-0 max-lg:shadow-none",
                  card &&
                    "lg:mx-auto lg:mt-6 lg:w-full lg:max-w-[40rem] lg:items-center lg:gap-6 lg:rounded-sheet lg:border-cv-border lg:px-10 lg:py-12 lg:text-center lg:shadow-floating",
                )
              : /* On a wide screen the corner is the lower one, above the step's pinned
                   bar. The top corner sat over the end of the workflow spine, hiding the
                   steps still ahead - what the reader checks while waiting - for as long
                   as the run lasted. */
                "fixed inset-x-4 top-[4.5rem] z-(--cv-z-toast) shadow-floating lg:inset-x-auto lg:end-6 lg:top-auto lg:bottom-28 lg:w-[22rem]",
            toneBorderClasses[tone],
            toneTextClasses[tone],
          )}
        >
          <div
            className={cx(
              "flex items-start gap-2.5",
              inline && "max-lg:flex-col max-lg:items-center max-lg:gap-4 max-lg:pt-2 max-lg:text-center",
              card && "lg:w-full lg:flex-col lg:items-center lg:gap-5",
            )}
          >
            {inline && eyebrow !== undefined ? (
              <p
                className={cx(
                  "self-stretch truncate text-start text-support text-cv-text-muted",
                  card ? "lg:text-center" : "lg:hidden",
                )}
                dir="auto"
              >
                {eyebrow}
              </p>
            ) : null}
            {inline ? (
              /* The run's mark: a ring that turns while it lives, round the sign of AI work,
                 or round the outcome's own icon once it has one. A phone's, and the wide
                 card's. */
              <span
                aria-hidden="true"
                className={cx("relative flex size-22 shrink-0 items-center justify-center", !card && "lg:hidden")}
              >
                <span className="absolute inset-0 rounded-pill border-4 border-cv-border" />
                <span
                  className={cx(
                    "absolute inset-0 rounded-pill border-4",
                    tone === "progress"
                      ? "border-transparent border-t-cv-accent motion-safe:animate-spin"
                      : "border-cv-accent",
                  )}
                />
                {tone === "progress" ? (
                  <Sparkles className="size-7 text-cv-text" />
                ) : (
                  <Icon className="size-7 text-cv-text" />
                )}
              </span>
            ) : null}
            <Icon
              aria-hidden="true"
              className={cx(
                "mt-0.5 size-icon-md shrink-0",
                tone === "progress" && "animate-spin",
                inline && "max-lg:hidden",
                card && "lg:hidden",
              )}
            />
            <div className={cx("min-w-0 flex-1 text-support", card && "lg:flex lg:flex-col lg:gap-2")}>
              <h2
                className={cx(
                  "font-semibold text-cv-text",
                  inline && "max-lg:text-heading-md max-lg:font-extrabold",
                  card && "lg:text-heading-md lg:font-extrabold",
                )}
                id={panelHeadingId}
              >
                {heading}
              </h2>
              <p className={cx("text-cv-text-muted", card && "lg:text-body")}>{statusText}</p>
            </div>
            {showingSuccess || inline ? null : (
              <IconButton
                aria-label="סגירה"
                className="-m-2"
                onClick={() => setSession((current) => ({ ...current, panelHidden: true }))}
                size="sm"
                variant="quiet"
              >
                <X aria-hidden="true" className="size-icon-md" />
              </IconButton>
            )}
          </div>
          {showingSuccess ? null : record === undefined || continuing ? (
            <p className="text-support leading-6 text-cv-text-muted" dir="auto">
              {continuation ?? pending?.note ?? "ההרצה נשלחה. המצב שלה יופיע כאן מיד."}
            </p>
          ) : (
            <>
              <div
                className={cx(
                  inline &&
                    "max-lg:flex max-lg:flex-col max-lg:gap-3 max-lg:rounded-surface max-lg:border max-lg:border-cv-border max-lg:bg-cv-surface max-lg:p-4",
                  card && "lg:w-full lg:rounded-surface lg:bg-cv-surface-muted lg:px-8 lg:py-6",
                )}
              >
                {/* The list's own name, shown where the steps get a card of their own. */}
                {inline ? (
                  <p aria-hidden="true" className="text-support font-bold text-cv-text lg:hidden">
                    שלבי ההרצה
                  </p>
                ) : null}
                <OperationPhaseSteps
                  activeNote={activeNote}
                  phase={record.phase}
                  prominent={card}
                  stackOnPhone={inline}
                />
              </div>
              {/* In place of the page's own content, the card says what fills it. */}
              {inline ? (
                <p className="flex items-start gap-2 text-support leading-6 text-cv-text-muted">
                  <Info aria-hidden="true" className="mt-1 size-icon-md shrink-0 lg:hidden" />
                  <span>{inlineNote}</span>
                </p>
              ) : null}
            </>
          )}
          {showingSuccess ? null : (
            <button
              aria-haspopup="dialog"
              className={cx(
                "w-fit text-support font-medium text-cv-text underline underline-offset-4",
                inline && "max-lg:min-h-11 max-lg:self-center",
                card && "lg:self-center",
              )}
              onClick={openDialog}
              type="button"
            >
              פירוט ההרצה
            </button>
          )}
          {card &&
          !isPhone &&
          !showingSuccess &&
          record !== undefined &&
          !continuing &&
          !isTerminalOperation(record) ? (
            <OperationRunActions operation={record} />
          ) : null}
        </section>
      ) : null}

      {card &&
      isPhone &&
      showPanel &&
      !showingSuccess &&
      record !== undefined &&
      !continuing &&
      !isTerminalOperation(record) ? (
        <OperationRunBar operation={record} />
      ) : null}

      <LiveRegion>{announcement}</LiveRegion>

      <Dialog
        headingId={headingId}
        onClose={() => setSession((current) => ({ ...current, dialogOpen: false }))}
        open={session.dialogOpen}
        {...(navigating ? {} : { restoreFocusTo: chipRef })}
        {...(failure === null
          ? {}
          : {
              /* The status word tells a failure from a cancellation or an interruption,
                 as the report's callout did. A phone's design line leaves it out, so
                 there it is for assistive tech only. */
              description: (
                <>
                  {heading} · הפעולה לא בוצעה
                  {record === undefined ? null : (
                    <span className="max-lg:sr-only"> · {statusLabels[record.status]}</span>
                  )}
                </>
              ),
              icon: (
                <span className="flex size-16 items-center justify-center rounded-pill bg-cv-accent text-cv-on-accent">
                  <TriangleAlert className="size-7" />
                </span>
              ),
            })}
        title={failure === null ? heading : failure.title}
      >
        {failure !== null && record !== undefined ? (
          <OperationFailurePage
            failureAction={failureAction}
            onClose={() => setSession((current) => ({ ...current, dialogOpen: false }))}
            onQueued={onQueued}
            operation={record}
            summary={failure}
          />
        ) : record === undefined ? (
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
            onNavigate={() => {
              setNavigating(true);
              setSession((current) => ({ ...current, dialogOpen: false }));
            }}
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
