import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import type { ApplicationListItem, RecruitmentStatus } from "@/api/contracts";
import { returnedApplicationId } from "@/navigation/boardReturn";
import { routePaths } from "@/navigation/routePaths";
import { RecruitmentUpdateDialog } from "@/features/recruitment";
import { Button, buttonClasses } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { IconButton } from "@/ui/IconButton";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { SuccessNotice } from "@/ui/SuccessNotice";
import { PageShell } from "@/ui/PageShell";
import { QueryState } from "@/ui/QueryState";
import { LiveRegion } from "@/ui/LiveRegion";
import { ApplicationAttentionSummary } from "../components/ApplicationAttentionSummary";
import { ApplicationCardsSkeleton } from "../components/ApplicationCardsView";
import { ApplicationDetailsDialog } from "../components/ApplicationDetailsDialog";
import { ApplicationListResults } from "../components/ApplicationListResults";
import { ApplicationListToolbar } from "../components/ApplicationListToolbar";
import { ApplicationPresetTabs } from "../components/ApplicationPresetTabs";
import { CloseApplicationDialog } from "../components/CloseApplicationDialog";
import { DeleteApplicationDialog } from "../components/DeleteApplicationDialog";
import { useApplicationListMutations } from "../api/mutations";
import { useApplicationListQuery } from "../hooks/useApplicationListQuery";
import { PAGE_SIZE } from "../model/applicationListParams";
import { initialViewMode, rememberViewMode, type ViewMode } from "../model/applicationViews";
import { type RecruitmentStageId, recruitmentStages, selectedStage } from "../model/recruitmentStages";

/* How long the card the reader came back from stays marked. Matches `cv-returned`. */
const RETURN_HIGHLIGHT_MS = 2_400;

const findApplication = (items: readonly ApplicationListItem[], id: string | null) =>
  id === null ? null : (items.find((item) => item.id === id) ?? null);

interface ClosedResult {
  applicationId: string;
  eventId: string | null;
  label: string;
  previousStatus: RecruitmentStatus;
}

/* The board reads top to bottom as four answers: where the reader is, what is waiting
   for them, which slice of the work they are looking at, and the work itself.

   The one action that starts something - a new Application - is the shell's, not this
   screen's, and is on screen already; repeating it here would give the reader two
   buttons for one thing. The empty database is the exception: there is no board to act
   on yet, so the offer is the only thing on the page. */
export const ApplicationListPage = () => {
  const { listQuery, query, searchInput, setSearchInput, updateQuery } = useApplicationListQuery();
  const [viewMode, setViewModeState] = useState<ViewMode>(initialViewMode);
  const setViewMode = (next: ViewMode) => {
    rememberViewMode(next);
    setViewModeState(next);
  };
  const [closingApplicationId, setClosingApplicationId] = useState<string | null>(null);
  const [closedResult, setClosedResult] = useState<ClosedResult | null>(null);
  const [deletingApplicationId, setDeletingApplicationId] = useState<string | null>(null);
  const [deletedLabel, setDeletedLabel] = useState<string | null>(null);
  const [updatingApplicationId, setUpdatingApplicationId] = useState<string | null>(null);
  const [detailsApplicationId, setDetailsApplicationId] = useState<string | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  /* Read once, from the link that left a flow screen. The history entry is then cleared
     of it, so a reload or a step back to this board does not mark the card again. */
  const [returnedId, setReturnedId] = useState(() => returnedApplicationId(location.state));
  useEffect(() => {
    if (returnedApplicationId(location.state) === null) return;
    void navigate({ pathname: location.pathname, search: location.search }, { replace: true, state: null });
  }, [location, navigate]);
  const { clearNextActionMutation, closeMutation, deleteMutation, undoCloseMutation } = useApplicationListMutations({
    onApplicationClosed: (applicationId, eventId) => {
      const application = findApplication(items, applicationId);
      setClosingApplicationId(null);
      if (application !== null) {
        setClosedResult({
          applicationId,
          eventId: eventId ?? null,
          label: application.company,
          previousStatus: application.recruitment_status as RecruitmentStatus,
        });
      }
    },
    onApplicationDeleted: (applicationId) => {
      const application = findApplication(items, applicationId);
      setDeletingApplicationId(null);
      setDeletedLabel(application?.company ?? null);
    },
    onCloseUndone: () => setClosedResult(null),
    onNextActionCleared: (applicationId) => {
      if (updatingApplicationId === applicationId) setUpdatingApplicationId(null);
    },
  });

  const page = listQuery.data;
  const items = page?.items ?? [];
  const loaded = page !== undefined;

  /* Once the board holds the card, bring it into view if it is not, and let its mark go
     after a moment. The board's order is untouched: the reader finds the card where it
     is, rather than the card being moved to where the reader is. */
  useEffect(() => {
    if (returnedId === null || !loaded) return;
    const card = [...window.document.querySelectorAll<HTMLElement>("[data-application-id]")].find(
      (element) => element.dataset.applicationId === returnedId,
    );
    if (card !== undefined) {
      const box = card.getBoundingClientRect();
      if (box.top < 0 || box.bottom > window.innerHeight) {
        const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
        card.scrollIntoView?.({ behavior: still ? "auto" : "smooth", block: "center" });
      }
    }
    const timeout = window.setTimeout(() => setReturnedId(null), RETURN_HIGHLIGHT_MS);
    return () => window.clearTimeout(timeout);
  }, [loaded, returnedId]);
  const closingApplication = findApplication(items, closingApplicationId);
  const deletingApplication = findApplication(items, deletingApplicationId);
  const updatingApplication = findApplication(items, updatingApplicationId);
  const detailsApplication = findApplication(items, detailsApplicationId);
  const clearingApplicationId = clearNextActionMutation.isPending ? (clearNextActionMutation.variables ?? null) : null;
  const recruitmentStageCounts = Object.fromEntries(
    recruitmentStages.map((stage) => [
      stage.id,
      stage.statuses.reduce((count, status) => count + (page?.recruitment_status_counts[status] ?? 0), 0),
    ]),
  ) as Partial<Record<RecruitmentStageId, number>>;

  /* Sorting orders the page rather than narrowing it, so it is neither part of "the
     list is filtered" nor undone by clearing the filters. */
  const filtered =
    query.preset !== undefined ||
    searchInput !== "" ||
    (query.activity ?? "open") !== "open" ||
    (query.stages?.length ?? 0) > 0 ||
    (query.recruitmentStatuses?.length ?? 0) > 0;
  const clearFilters = () => updateQuery({ sort: query.sort });
  const undoClose = () => {
    if (closedResult === null || closedResult.eventId === null) return;
    undoCloseMutation.mutate({ ...closedResult, eventId: closedResult.eventId });
  };

  /* The named slices sit in the masthead, beside the title: they are the first choice
     the reader makes, and reading them on the same line as the page name says which
     board is on screen. They appear once there is a board to slice. */
  const presetTabs =
    page === undefined || page.total === 0 ? undefined : (
      <div className="self-center">
        <ApplicationPresetTabs
          counts={page.preset_counts}
          onSelect={(preset) => updateQuery({ ...query, preset: preset === "all" ? undefined : preset })}
          value={query.preset ?? "all"}
        />
      </div>
    );

  return (
    <PageShell
      actions={presetTabs}
      description="איפה עומד כל תהליך גיוס, ומה עוד צריך לקורות החיים."
      measure="wide"
      title="לוח מועמדויות"
    >
      {/* The closed card leaves the board, so the way back floats where the reader's eye
          already is rather than at the top of a list they may have scrolled away from.
          It has no timer: the correction stays valid, so the offer stays until the
          reader takes it or puts it away. */}
      {closedResult === null ? null : (
        <div className="fixed inset-x-4 bottom-4 z-(--cv-z-toast) mx-auto flex max-w-xl flex-wrap items-center justify-between gap-3 rounded-surface border border-cv-border bg-cv-surface-raised px-3.5 py-2.5 text-support text-cv-text shadow-floating">
          <LiveRegion className="min-w-0 flex-1" visuallyHidden={false}>
            <span dir="auto">המועמדות של {closedResult.label} נסגרה והועברה למועמדויות הסגורות.</span>
          </LiveRegion>
          <div className="flex items-center gap-1">
            {closedResult.eventId === null ? null : (
              <Button
                onClick={undoClose}
                pending={undoCloseMutation.isPending}
                pendingLabel="מבטל סגירה…"
                size="compact"
                variant="secondary"
              >
                ביטול הסגירה
              </Button>
            )}
            <IconButton aria-label="סגירת ההודעה" onClick={() => setClosedResult(null)}>
              <X aria-hidden="true" className="size-icon-md" />
            </IconButton>
          </div>
        </div>
      )}
      {deletedLabel === null ? null : (
        <SuccessNotice
          onDismiss={() => setDeletedLabel(null)}
          title={`המועמדות של ${deletedLabel} נמחקה והוסרה מהלוח`}
        />
      )}
      <ApplicationAttentionSummary
        boardHasApplications={page !== undefined && page.total > 0}
        clearingApplicationId={clearingApplicationId}
        filterActive={query.preset === "needs_attention"}
        onClearNextAction={(application) => clearNextActionMutation.mutate(application.id)}
        onOpenStatusDialog={(application) => setUpdatingApplicationId(application.id)}
        onShowAll={() => updateQuery({ ...query, preset: "needs_attention" })}
      />
      {clearNextActionMutation.error === null ? null : (
        <ErrorCallout error={clearNextActionMutation.error} fallbackDetail="אפשר לנסות שוב." title="התזכורת לא הוסרה" />
      )}
      {closeMutation.error === null ? null : (
        <ErrorCallout error={closeMutation.error} fallbackDetail="אפשר לנסות שוב." title="המועמדות לא נסגרה" />
      )}
      {undoCloseMutation.error === null ? null : (
        <ErrorCallout
          error={undoCloseMutation.error}
          fallbackDetail="המועמדות נשארה סגורה. אפשר לנסות שוב או לתקן את האירוע מתוך המועמדות."
          title="הסגירה לא בוטלה"
        />
      )}
      {deleteMutation.error === null ? null : (
        <ErrorCallout error={deleteMutation.error} fallbackDetail="אפשר לנסות שוב." title="המועמדות לא נמחקה" />
      )}

      <QueryState
        empty={page?.total === 0}
        emptyState={
          <EmptyState className="bg-cv-surface">
            <p className="text-body text-cv-text">עוד לא נוצרה אף מועמדות.</p>
            <p className="mt-1 text-support text-cv-text-muted">מועמדות חדשה מתחילה בהדבקת מודעת המשרה.</p>
            <div className="mt-5 flex justify-center">
              <Link className={buttonClasses("primary")} to={routePaths.newApplication}>
                משרה חדשה
              </Link>
            </div>
          </EmptyState>
        }
        error={listQuery.error}
        errorTitle="לא ניתן לטעון את המועמדויות"
        loading={listQuery.isPending}
        onRetry={() => void listQuery.refetch()}
        /* No `loadingLabel`: `loadingState` always wins over it, so a label here would be
           a string that never renders. The skeleton announces the wait itself. */
        loadingState={<ApplicationCardsSkeleton />}
      >
        {page === undefined ? null : (
          <div className="flex flex-col gap-4">
            <ApplicationListToolbar
              activity={query.activity ?? "open"}
              filtered={filtered}
              onActivityChange={(activity) => updateQuery({ ...query, activity })}
              onClearFilters={clearFilters}
              onPreparationStateChange={(stage) => updateQuery({ ...query, stages: stage ? [stage] : [] })}
              onRecruitmentStageChange={(stageId) => {
                const stage = recruitmentStages.find((candidate) => candidate.id === stageId);
                updateQuery({ ...query, recruitmentStatuses: stage?.statuses ?? [] });
              }}
              onSearchChange={setSearchInput}
              onSortChange={(sort) => updateQuery({ ...query, sort })}
              onViewModeChange={setViewMode}
              preparationState={query.stages?.[0]}
              recruitmentStage={selectedStage(query.recruitmentStatuses)}
              recruitmentStageCounts={recruitmentStageCounts}
              resultSummary={
                page.matched === page.total
                  ? `${page.total} מועמדויות`
                  : !filtered
                    ? `${page.matched} מתוך ${page.total} מועמדויות · תהליכים סגורים מוסתרים`
                    : `${page.matched} מתוך ${page.total} מועמדויות`
              }
              search={searchInput}
              sort={query.sort ?? "updated"}
              stageCounts={page.stage_counts}
              viewMode={viewMode}
            />
            <ApplicationListResults
              clearingApplicationId={clearingApplicationId}
              replacing={listQuery.isPlaceholderData}
              items={items}
              matchedCount={page.matched}
              offset={query.offset ?? 0}
              onClearFilters={clearFilters}
              onClearNextAction={(application) => clearNextActionMutation.mutate(application.id)}
              onOffsetChange={(offset) => updateQuery({ ...query, offset }, { replace: false, resetOffset: false })}
              onRequestClose={(item) => setClosingApplicationId(item.id)}
              onRequestDelete={(item) => setDeletingApplicationId(item.id)}
              onRequestDetails={(item) => setDetailsApplicationId(item.id)}
              onRequestUpdate={(item) => setUpdatingApplicationId(item.id)}
              pageSize={PAGE_SIZE}
              recruitmentStatusCounts={page.recruitment_status_counts}
              recruitmentStatusFilter={query.recruitmentStatuses}
              returnedId={returnedId}
              viewMode={viewMode}
            />
          </div>
        )}
      </QueryState>
      <CloseApplicationDialog
        application={closingApplication}
        onCancel={() => setClosingApplicationId(null)}
        onConfirm={() => closingApplicationId && closeMutation.mutate(closingApplicationId)}
        pending={closeMutation.isPending}
      />
      <DeleteApplicationDialog
        application={deletingApplication}
        onCancel={() => setDeletingApplicationId(null)}
        onConfirm={() => deletingApplicationId && deleteMutation.mutate(deletingApplicationId)}
        pending={deleteMutation.isPending}
      />
      <ApplicationDetailsDialog
        application={detailsApplication}
        clearing={detailsApplication !== null && clearingApplicationId === detailsApplication.id}
        onClearNextAction={(application) => clearNextActionMutation.mutate(application.id)}
        onClose={() => setDetailsApplicationId(null)}
        onRequestUpdate={(application) => setUpdatingApplicationId(application.id)}
      />
      <RecruitmentUpdateDialog application={updatingApplication} onClose={() => setUpdatingApplicationId(null)} />
    </PageShell>
  );
};
