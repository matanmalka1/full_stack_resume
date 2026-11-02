import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Download, Pencil } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { watchedApplicationDetailQueryOptions } from "@/api/applications";
import type { ApplicationDetail } from "@/api/contracts";
import { documentPdfHref } from "@/api/documents";
import { RecruitmentHistoryDialog, RecruitmentUpdateDialog } from "@/features/recruitment";
import { boardPath, boardReturnState } from "@/navigation/boardReturn";
import { routePaths } from "@/navigation/routePaths";
import { useRequiredParam } from "@/navigation/useRequiredParam";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { CommitBar } from "@/ui/CommitBar";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { initialOf } from "@/ui/InitialTile";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { showToast } from "@/ui/toast";
import { formatDateTime } from "@/utils/formatDateTime";
import { useApplicationRecordMutations } from "../api/mutations";
import { ApplicationActionsMenu } from "../components/ApplicationActionsMenu";
import { ApplicationDetailsSheet } from "../components/ApplicationDetailsSheet";
import { ApplicationFacts } from "../components/ApplicationFacts";
import { CloseApplicationDialog } from "../components/CloseApplicationDialog";
import { DeleteApplicationDialog } from "../components/DeleteApplicationDialog";
import { JobPostingCard } from "../components/JobPostingCard";
import { JobPostingDialog, jobPostingEditable } from "../components/JobPostingDialog";
import { NextActionCard } from "../components/NextActionCard";
import { PreparationProgressCard } from "../components/PreparationProgressCard";
import { RecruitmentStageCard } from "../components/RecruitmentStageCard";
import { continuation, isApplicationClosed } from "../model/applicationHub";

type HubDialog = "update" | "details" | "history" | "posting" | "close" | "delete";

/* The cards' own shapes while the record is read, so the screen fills in rather than
   replacing a sentence with a page. */
const hubLoading = (
  <div className="flex flex-col gap-4">
    <LiveRegion>טוען את פרטי המועמדות…</LiveRegion>
    <Skeleton className="block h-28 w-full" />
    <Skeleton className="block h-40 w-full" />
    <Skeleton className="block h-14 w-full" />
  </div>
);

/* The PDF of a Ready document, or the same control disabled with the reason in its name:
   the place where the file will be is shown before there is one. */
const DownloadControl = ({ detail, placement }: { detail: ApplicationDetail; placement: "phone" | "desktop" }) => {
  const href =
    detail.preparation_state === "ready" && detail.document_hash != null
      ? documentPdfHref(detail.application.id, detail.document_hash)
      : null;
  const classes =
    placement === "phone" ? buttonClasses("secondary", undefined, "icon") : buttonClasses("secondary", "w-full");
  const content = (
    <>
      <Download aria-hidden="true" className="size-icon-lg" />
      {placement === "desktop" ? "הורדת PDF" : null}
    </>
  );

  return href === null ? (
    <button aria-label="הורדת קורות החיים, זמינה כשקורות החיים מוכנים" className={classes} disabled type="button">
      {content}
    </button>
  ) : (
    <a aria-label="הורדת קורות החיים כקובץ PDF" className={classes} href={href}>
      {content}
    </a>
  );
};

/* One Application as a record: where it stands with the employer, where its CV stands,
   the reminder the reader set, the posting, and the one command forward.

   It is not a step of the CV wizard - the analysis, the draft and the ready document each
   have a screen of their own (`AnalysisPage`, the editor, the ready step) - but the place
   the steps hang from: its checklist links to each, and its command opens the one the
   work is waiting on. The employer's side is managed here, through the status sheet and
   the record's menu, because it is a fact about the record rather than about any step.

   A phone reads it as a column of cards under the record's name, the command pinned at
   the bottom beside the PDF; a wide screen puts the commands in the header and the
   reminder, the record's facts and the PDF in a side column. */
export const ApplicationPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const location = useLocation();
  const navigate = useNavigate();
  const query = useQuery(watchedApplicationDetailQueryOptions(applicationId));
  const detail = query.data;
  const [dialog, setDialog] = useState<HubDialog | null>(null);
  const { closeMutation, deleteMutation } = useApplicationRecordMutations(applicationId, {
    onDeleted: () => void navigate(boardPath(), { state: boardReturnState(applicationId) }),
  });

  /* The intake screen hands a new Application over in route state, with the analysis it
     queued: that wait is the analysis step's to report, so the news goes on there. */
  const routeState = location.state as { createdApplication?: unknown } | null;
  if (routeState?.createdApplication !== undefined) {
    return <Navigate replace state={location.state} to={routePaths.analysis(applicationId)} />;
  }

  const application = detail?.application;
  const deleted = application?.deleted_at != null;
  const closed = detail === undefined ? false : isApplicationClosed(detail);
  const next = detail === undefined || deleted ? null : continuation(detail);
  const target =
    application === undefined
      ? null
      : { company: application.company, id: application.id, target_role: application.target_role };
  const open = (which: HubDialog) => () => setDialog(which);
  const actions = {
    onClose: open("close"),
    onDelete: open("delete"),
    onDetails: open("details"),
    onHistory: open("history"),
    onUpdate: open("update"),
    ...(detail !== undefined && jobPostingEditable(detail) ? { onEditPosting: open("posting") } : {}),
  };

  return (
    <section
      aria-labelledby="route-heading"
      className="page-frame max-lg:flex max-lg:min-h-[calc(100dvh-2.5rem)] max-lg:flex-col"
    >
      {/* A phone's header row: the way back to the board, and the record's menu. */}
      <div className="-mx-2 -mt-2 mb-1 flex items-center justify-between lg:hidden">
        <Link
          aria-label="חזרה ללוח המועמדויות"
          className="flex size-11 items-center justify-center rounded-control text-cv-text transition-colors hover:bg-cv-surface-muted"
          state={boardReturnState(applicationId)}
          to={boardPath()}
        >
          <ChevronRight aria-hidden="true" className="size-icon-lg" />
        </Link>
        {application === undefined || deleted ? null : (
          <ApplicationActionsMenu {...actions} closed={closed} company={application.company} placement="phone" />
        )}
      </div>

      <nav aria-label="מיקום" className="mb-5.5 flex gap-1.5 text-support text-cv-text-muted max-lg:hidden">
        <Link
          className="underline underline-offset-4 hover:text-cv-text"
          state={boardReturnState(applicationId)}
          to={boardPath()}
        >
          לוח המועמדויות
        </Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page" dir="auto">
          {application?.target_role ?? "פרטי משרה"}
        </span>
      </nav>

      <div className="flex flex-wrap items-center gap-3.5 lg:gap-4">
        <span
          aria-hidden="true"
          className="flex size-14 shrink-0 items-center justify-center rounded-surface border border-cv-hairline bg-cv-surface text-heading-md font-extrabold text-cv-text lg:size-16 lg:rounded-fab lg:text-title"
        >
          {application === undefined ? null : initialOf(application.company)}
        </span>
        <div className="min-w-0 flex-1 lg:min-w-55">
          {/* Held at one line's width while the projection is in flight, so the name does
              not move the page under the reader when it arrives. */}
          <h1
            className="text-heading-md font-extrabold tracking-tight text-cv-text lg:text-display"
            data-route-heading
            dir="auto"
            id="route-heading"
            tabIndex={-1}
          >
            {application === undefined ? (
              <Skeleton className="inline-block w-56 max-w-full align-middle" />
            ) : (
              application.target_role
            )}
          </h1>
          {application === undefined ? null : (
            <p className="mt-0.5 text-label text-cv-text-muted lg:mt-1 lg:text-body" dir="auto">
              {application.company} · נקלטה ב־{formatDateTime(application.created_at, "date")}
            </p>
          )}
        </div>
        {application === undefined || deleted || next === null ? null : (
          <div className="flex items-center gap-2 max-lg:hidden">
            <Button onClick={actions.onUpdate} size="default" variant="secondary">
              עדכון סטטוס
            </Button>
            <ApplicationActionsMenu {...actions} closed={closed} company={application.company} placement="desktop" />
            <Link className={buttonClasses("primary", "shadow-action")} to={next.to}>
              {next.label}
            </Link>
          </div>
        )}
      </div>

      <div className="mt-4 flex flex-col gap-4 lg:mt-5.5">
        {closeMutation.error === null ? null : (
          <ErrorCallout error={closeMutation.error} fallbackDetail="אפשר לנסות שוב." title="המועמדות לא נסגרה" />
        )}
        {deleteMutation.error === null ? null : (
          <ErrorCallout error={deleteMutation.error} fallbackDetail="אפשר לנסות שוב." title="המועמדות לא נמחקה" />
        )}

        <QueryState
          error={query.error}
          errorTitle="לא ניתן לטעון את פרטי המועמדות"
          loading={detail === undefined}
          loadingState={hubLoading}
          onRetry={() => void query.refetch()}
        >
          {detail === undefined || next === null ? (
            deleted ? (
              /* A deleted Application stays reachable by ID (product-spec.md invariant #20)
                 so its history is never orphaned, but no command is offered against it. */
              <Callout role="alert" title="המועמדות הזו נמחקה" tone="warning">
                המועמדות הוסרה מלוח המועמדויות ואין לבצע עליה פעולות נוספות. נוסח המשרה, הניתוח, מסמך קורות החיים
                וההגשות שנרשמו נשארים בדיוק כפי שהם.
              </Callout>
            ) : null
          ) : (
            <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_18.75rem] lg:gap-6">
              <div className="flex min-w-0 flex-col gap-4 lg:gap-4.5">
                <RecruitmentStageCard detail={detail} onUpdate={actions.onUpdate} />
                <div className="lg:hidden">
                  <NextActionCard detail={detail} headingId="next-action-heading-phone" onUpdate={actions.onUpdate} />
                </div>
                <PreparationProgressCard detail={detail} />
                <JobPostingCard detail={detail} />
              </div>
              <aside aria-label="פרטי המועמדות" className="flex flex-col gap-3.5 max-lg:hidden">
                <NextActionCard detail={detail} headingId="next-action-heading" onUpdate={actions.onUpdate} />
                <ApplicationFacts detail={detail} />
                <DownloadControl detail={detail} placement="desktop" />
              </aside>
            </div>
          )}
        </QueryState>
      </div>

      {/* A phone's command, pinned to the screen's bottom edge beside the PDF. The page is
          a column at least the screen's height, so a short record still puts it there. */}
      {detail === undefined || next === null ? null : (
        <div className="-mb-6 pt-4 max-lg:mt-auto lg:hidden">
          <CommitBar
            primary={
              <Link className={buttonClasses("primary", "shadow-action", "large")} to={next.to}>
                {next.to === routePaths.draft(applicationId) ? (
                  <Pencil aria-hidden="true" className="size-icon-md" />
                ) : null}
                {next.label}
                {next.to === routePaths.draft(applicationId) ? null : (
                  <ChevronLeft aria-hidden="true" className="size-icon-md" />
                )}
              </Link>
            }
            secondary={<DownloadControl detail={detail} placement="phone" />}
            secondaryIconOnly
          />
        </div>
      )}

      <RecruitmentUpdateDialog application={dialog === "update" ? target : null} onClose={() => setDialog(null)} />
      <RecruitmentHistoryDialog application={dialog === "history" ? target : null} onClose={() => setDialog(null)} />
      <ApplicationDetailsSheet
        application={
          dialog === "details" && detail !== undefined
            ? {
                ...detail.application,
                closed,
                preparation_state: detail.preparation_state,
                recommended_action: detail.recommended_action,
                recruitment_status: detail.recruitment_status,
              }
            : null
        }
        continueTo={next === null ? null : { label: "המשך בהכנה", to: next.to }}
        onClose={() => setDialog(null)}
      />
      {dialog === "posting" && detail !== undefined ? (
        <JobPostingDialog
          detail={detail}
          onClose={() => setDialog(null)}
          onSaved={() => {
            setDialog(null);
            showToast({
              body: "הניתוח הקודם נעשה על הנוסח הקודם ואינו פעיל יותר, ולכן יש להריץ ניתוח מחדש.",
              title: "נוסח המשרה עודכן",
            });
          }}
        />
      ) : null}
      <CloseApplicationDialog
        application={dialog === "close" ? (target ?? null) : null}
        onCancel={() => setDialog(null)}
        onConfirm={() =>
          closeMutation.mutate(undefined, {
            onSettled: () => setDialog(null),
            onSuccess: () =>
              showToast({ body: "היא ירדה מלוח המועמדויות הפעילות, ושום דבר בה לא נמחק.", title: "המועמדות נסגרה" }),
          })
        }
        pending={closeMutation.isPending}
      />
      <DeleteApplicationDialog
        application={dialog === "delete" ? (target ?? null) : null}
        onCancel={() => setDialog(null)}
        onConfirm={() => deleteMutation.mutate(undefined, { onSettled: () => setDialog(null) })}
        pending={deleteMutation.isPending}
      />
    </section>
  );
};
