import { Info, RefreshCw, ShieldCheck, Sparkle, TriangleAlert, X } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { Operation } from "@/api/contracts";
import { boardPath, boardReturnState } from "@/navigation/boardReturn";
import { routePaths } from "@/navigation/routePaths";
import { Button, buttonClasses } from "@/ui/Button";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { PhoneActionBar } from "@/ui/PhoneActionBar";
import { cx } from "@/ui/cx";
import { useCancelReveal } from "../hooks/useCancelReveal";
import { useIsPhone } from "@/ui/useIsPhone";
import { useOperationCommands } from "../hooks/useOperationCommands";
import type { FailureSummary } from "../model/failureSummary";
import { failedPhaseStep } from "../model/operationPhases";
import { OperationPhaseSteps } from "./OperationPhaseSteps";

/* A wide screen centres the run in the content column as one card; a phone gives it the
   whole screen, under a close mark and whose work it is. */
const cardClasses =
  "w-full max-w-160 rounded-sheet border border-cv-hairline bg-cv-surface p-10 shadow-floating max-lg:max-w-none max-lg:rounded-none max-lg:border-0 max-lg:bg-transparent max-lg:p-0 max-lg:shadow-none";

const PhoneTop = ({ closeTo, eyebrow }: { closeTo: string; eyebrow: ReactNode }) => (
  <div className="-ms-2 -mt-1.5 flex items-center justify-between gap-3 lg:hidden">
    <Link
      aria-label="סגירה"
      className="flex size-11 shrink-0 items-center justify-center rounded-control text-cv-text"
      to={closeTo}
    >
      <X aria-hidden="true" className="size-5.5" />
    </Link>
    {eyebrow === undefined ? null : (
      <p className="min-w-0 truncate text-caption text-cv-text-muted" dir="auto">
        {eyebrow}
      </p>
    )}
  </div>
);

const RouteHeading = ({ children, className }: { children: ReactNode; className?: string }) => (
  <h1
    className={cx("font-extrabold tracking-tight text-cv-text", className)}
    data-route-heading
    id="route-heading"
    tabIndex={-1}
  >
    {children}
  </h1>
);

/* A run that is the host screen's whole body, while it lives: the mark of AI work inside a
   turning ring, what is running and for whom, its steps, and the two ways on - leave for
   the board while it goes on, or stop it.

   Cancel is the record's own command, offered after the same delay the report waits, and
   only while the record says it can be cancelled. Before a record exists the run is on
   its first step and nothing can be cancelled yet. */
export const LiveRunScreen = ({
  activeNote,
  closeTo,
  eyebrow,
  heading,
  note,
  onQueued,
  record,
  resultNote,
}: {
  activeNote?: ReactNode;
  /* Where the phone's close mark leads: the record the run belongs to. */
  closeTo: string;
  eyebrow?: ReactNode;
  heading: ReactNode;
  /* The one-sentence account of what is running, announced as it changes. */
  note: ReactNode;
  onQueued: (operationId: string) => void;
  record: Operation | undefined;
  /* What fills this screen once the run ends. */
  resultNote: ReactNode;
}) => {
  const isPhone = useIsPhone();
  const actions =
    record === undefined ? (
      <BoardLink applicationId={undefined} />
    ) : (
      <>
        <CancelButton onQueued={onQueued} record={record} />
        <BoardLink applicationId={record.application_id} />
      </>
    );

  return (
    <div className="flex w-full flex-col items-center gap-5 lg:min-h-[calc(100dvh-4.5rem)] lg:justify-center">
      <PhoneTop closeTo={closeTo} eyebrow={eyebrow} />
      <section
        aria-labelledby="route-heading"
        className={cx(cardClasses, "flex flex-col items-center gap-6.5 text-center max-lg:gap-5.5 max-lg:pt-4")}
      >
        {eyebrow === undefined ? null : (
          <p className="text-support text-cv-text-muted max-lg:hidden" dir="auto">
            {eyebrow}
          </p>
        )}
        <span aria-hidden="true" className="relative flex size-28 items-center justify-center max-lg:size-24">
          <span className="absolute inset-0 rounded-pill border-[6px] border-cv-border" />
          <span className="absolute inset-0 rounded-pill border-[6px] border-transparent border-t-cv-accent motion-safe:animate-spin" />
          <Sparkle className="size-7 text-cv-accent" />
        </span>
        <div className="flex flex-col gap-2">
          <RouteHeading className="text-title max-lg:text-heading-md">{heading}</RouteHeading>
          <p className="text-body text-cv-text-muted" dir="auto">
            {note}
          </p>
        </div>

        <div className="w-full rounded-surface bg-cv-canvas p-4.5 max-lg:border max-lg:border-cv-hairline max-lg:bg-cv-surface max-lg:p-4 max-lg:text-start max-lg:shadow-surface">
          <p aria-hidden="true" className="mb-3 text-support font-bold text-cv-text-muted lg:hidden">
            שלבי ההרצה
          </p>
          <OperationPhaseSteps
            activeNote={activeNote}
            layout={isPhone ? "stacked" : "columns"}
            pending={record === undefined}
            phase={record?.phase ?? "queued"}
          />
        </div>

        <p className="flex items-start gap-2.5 text-label text-cv-text-muted max-lg:text-start">
          <Info aria-hidden="true" className="mt-1 size-icon-md shrink-0 lg:hidden" />
          <span>{resultNote}</span>
        </p>

        {isPhone ? null : <div className="flex flex-wrap justify-center gap-2.5">{actions}</div>}
      </section>
      {isPhone ? <PhoneActionBar>{actions}</PhoneActionBar> : null}
    </div>
  );
};

const BoardLink = ({ applicationId }: { applicationId: string | undefined }) => (
  <Link className={buttonClasses("primary", "max-lg:flex-1")} state={boardReturnState(applicationId)} to={boardPath()}>
    חזרה ללוח
  </Link>
);

const CancelButton = ({ onQueued, record }: { onQueued: (operationId: string) => void; record: Operation }) => {
  const revealed = useCancelReveal(record);
  const { cancel } = useOperationCommands(record, onQueued);
  if (!revealed || !record.available_actions.includes("cancel")) return null;
  return (
    <Button
      className="cv-settle-in max-lg:flex-1"
      onClick={() => cancel.mutate()}
      pending={cancel.isPending}
      pendingLabel="מבטל…"
      size="default"
      variant="secondary"
    >
      {cancel.error === null ? "ביטול הפעולה" : "הביטול נכשל · ניסיון נוסף"}
    </Button>
  );
};

/* A run that was the host screen's whole body and ended without a result: what happened,
   that nothing the reader had was lost, where the run stopped, and the ways on - back to
   the application, the run again, or Settings when a missing provider is the fix.

   The words are the catalogue's, as in the report: the server's own sentence is never
   shown. A retry that would fail the same way for want of a provider is not offered;
   Settings leads instead. */
export const FailedRunScreen = ({
  eyebrow,
  heading,
  onQueued,
  record,
  summary,
}: {
  eyebrow?: ReactNode;
  heading: ReactNode;
  onQueued: (operationId: string) => void;
  record: Operation;
  summary: FailureSummary;
}) => {
  const isPhone = useIsPhone();
  const { error, retry } = useOperationCommands(record, onQueued);
  const applicationPath = routePaths.application(record.application_id);
  const canRetry = !summary.missingProvider && record.available_actions.includes("retry");

  const settingsLink = summary.missingProvider ? (
    <Link
      className={buttonClasses(canRetry ? "secondary" : "primary", "max-lg:flex-1 lg:border-cv-border")}
      to={routePaths.settings}
    >
      להגדרות
    </Link>
  ) : null;
  const backLink = (
    <Link className={buttonClasses("secondary", "max-lg:flex-1")} to={applicationPath}>
      חזרה למועמדות
    </Link>
  );
  const retryButton = canRetry ? (
    <Button
      className="max-lg:flex-1"
      onClick={() => retry.mutate()}
      pending={retry.isPending}
      pendingLabel="יוצר ניסיון חדש…"
      size="default"
    >
      <RefreshCw aria-hidden="true" className="size-icon-md" />
      הרצה מחדש
    </Button>
  ) : null;

  const steps = <OperationPhaseSteps failedStep={failedPhaseStep(record.started_at)} from={1} phase={record.phase} />;
  const preserved = (
    <>
      <ShieldCheck aria-hidden="true" className="size-icon-md shrink-0" />
      המצב שהיה פעיל לפני הפעולה נשמר.
    </>
  );

  return (
    <div className="flex w-full flex-col items-center gap-5 lg:min-h-[calc(100dvh-4.5rem)] lg:justify-center">
      <PhoneTop closeTo={applicationPath} eyebrow={eyebrow} />
      <section
        aria-labelledby="route-heading"
        className={cx(cardClasses, "flex flex-col gap-5.5 max-lg:gap-5 max-lg:pt-4")}
      >
        <div className="flex items-center gap-4.5 max-lg:flex-col max-lg:gap-3.5 max-lg:text-center" role="alert">
          <span
            aria-hidden="true"
            className="flex size-16 shrink-0 items-center justify-center rounded-pill bg-cv-brand-deep text-cv-on-accent max-lg:size-20"
          >
            <TriangleAlert className="size-7 max-lg:size-8" />
          </span>
          <div>
            <p className="text-support font-bold text-cv-text-muted">{heading} · הפעולה לא בוצעה</p>
            <RouteHeading className="mt-1 text-title max-lg:text-heading-md">{summary.title}</RouteHeading>
          </div>
        </div>

        {isPhone ? (
          <>
            <section
              aria-labelledby="operation-failure-what"
              className="flex flex-col gap-3 rounded-surface border border-cv-hairline bg-cv-surface p-4 shadow-surface"
            >
              <h2 className="text-support font-bold text-cv-text-muted" id="operation-failure-what">
                מה קרה
              </h2>
              {summary.sentences.map((sentence) => (
                <p className="text-body leading-relaxed text-cv-text" dir="auto" key={sentence}>
                  {sentence}
                </p>
              ))}
              <p className="flex items-center gap-2 border-t border-cv-hairline pt-3 text-support text-cv-text-muted">
                {preserved}
              </p>
            </section>
            <section aria-labelledby="operation-failure-steps" className="flex flex-col gap-2">
              <h2 className="px-1 text-support font-bold text-cv-text-muted" id="operation-failure-steps">
                שלבי ההרצה
              </h2>
              <div className="rounded-surface border border-cv-hairline bg-cv-surface px-3.5 py-3 text-support">
                {steps}
              </div>
            </section>
          </>
        ) : (
          <>
            {summary.sentences.map((sentence) => (
              <p className="text-heading-sm leading-relaxed font-normal text-cv-text" dir="auto" key={sentence}>
                {sentence}
              </p>
            ))}
            <p className="flex items-center gap-2 rounded-control bg-cv-canvas px-3.5 py-3 text-label text-cv-text-muted">
              {preserved}
            </p>
            {steps}
          </>
        )}

        {error === null ? null : (
          <ErrorCallout error={error} fallbackDetail="המצב הקיים נשמר. אפשר לנסות שוב." title="הפעולה לא בוצעה" />
        )}

        {isPhone ? null : (
          <div className="flex flex-wrap justify-end gap-2.5 border-t border-cv-hairline pt-5.5">
            {settingsLink}
            {backLink}
            {retryButton}
          </div>
        )}
      </section>
      {isPhone ? (
        <PhoneActionBar>
          {backLink}
          {retryButton ?? settingsLink}
        </PhoneActionBar>
      ) : null}
    </div>
  );
};
