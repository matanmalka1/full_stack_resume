import { useState } from "react";
import { Link } from "react-router-dom";

import type { ApplicationListItem, RecruitmentStatus } from "@/api/contracts";
import { routePaths } from "@/app/routePaths";
import { RecruitmentUpdateDialog } from "@/features/recruitment";
import { Button, buttonClasses } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { PageShell } from "@/ui/PageShell";
import { QueryState } from "@/ui/QueryState";
import { LiveRegion } from "@/ui/LiveRegion";
import { ApplicationAttentionSummary } from "../components/ApplicationAttentionSummary";
import { ApplicationListResults } from "../components/ApplicationListResults";
import { ApplicationListToolbar } from "../components/ApplicationListToolbar";
import { ApplicationListTableSkeleton } from "../components/ApplicationListTable";
import { CloseApplicationDialog } from "../components/CloseApplicationDialog";
import { useApplicationListMutations } from "../api/mutations";
import { useApplicationListQuery } from "../hooks/useApplicationListQuery";
import { PAGE_SIZE } from "../model/applicationListParams";
import { initialViewMode, type ViewMode } from "../model/applicationViews";
import { type RecruitmentStageId, recruitmentStages, selectedStage } from "../model/recruitmentStages";

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
  const [viewMode, setViewMode] = useState<ViewMode>(initialViewMode);
  const [closingApplicationId, setClosingApplicationId] = useState<string | null>(null);
  const [closedResult, setClosedResult] = useState<ClosedResult | null>(null);
  const [updatingApplicationId, setUpdatingApplicationId] = useState<string | null>(null);
  const { clearNextActionMutation, closeMutation, undoCloseMutation } = useApplicationListMutations({
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
    onCloseUndone: () => setClosedResult(null),
    onNextActionCleared: (applicationId) => {
      if (updatingApplicationId === applicationId) setUpdatingApplicationId(null);
    },
  });

  const page = listQuery.data;
  const items = page?.items ?? [];
  const closingApplication = findApplication(items, closingApplicationId);
  const updatingApplication = findApplication(items, updatingApplicationId);
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

  return (
    <PageShell measure="wide" title="לוח מועמדויות">
      {closedResult === null ? null : (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-cv-success/20 bg-cv-success-soft/60 px-3.5 py-2.5 text-support text-cv-text">
          <LiveRegion visuallyHidden={false}>
            <span dir="auto">המועמדות של {closedResult.label} נסגרה והועברה למועמדויות הסגורות.</span>
          </LiveRegion>
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
        </div>
      )}
      <ApplicationAttentionSummary
        clearingApplicationId={clearNextActionMutation.isPending ? (clearNextActionMutation.variables ?? null) : null}
        onClearNextAction={(application) => clearNextActionMutation.mutate(application.id)}
        onOpenStatusDialog={(application) => setUpdatingApplicationId(application.id)}
      />
      {clearNextActionMutation.error === null ? null : (
        <ErrorCallout
          error={clearNextActionMutation.error}
          fallbackDetail="התזכורת לא הוסרה. הערכים הקיימים לא השתנו."
          fallbackTitle="לא ניתן להסיר את התזכורת"
        />
      )}
      {closeMutation.error === null ? null : (
        <ErrorCallout
          error={closeMutation.error}
          fallbackDetail="המועמדות לא נסגרה. אפשר לנסות שוב."
          fallbackTitle="סגירת המועמדות נכשלה"
        />
      )}
      {undoCloseMutation.error === null ? null : (
        <ErrorCallout
          error={undoCloseMutation.error}
          fallbackDetail="הסגירה נשארה בתוקף. אפשר לנסות שוב או לתקן את האירוע מתוך המועמדות."
          fallbackTitle="לא ניתן לבטל את הסגירה"
        />
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
        fallbackTitle="לא ניתן לטעון את המועמדויות"
        loading={listQuery.isPending}
        loadingLabel="טוען את המועמדויות…"
        loadingState={<ApplicationListTableSkeleton />}
      >
        {page === undefined ? null : (
          <div className="flex flex-col gap-4">
            <ApplicationListToolbar
              activity={query.activity ?? "open"}
              filtered={filtered}
              onActivityChange={(activity) => updateQuery({ ...query, activity })}
              onClearFilters={clearFilters}
              onPreparationStateChange={(stage) => updateQuery({ ...query, stages: stage ? [stage] : [] })}
              onPresetSelect={(preset) => updateQuery({ ...query, preset: preset === "all" ? undefined : preset })}
              onRecruitmentStageChange={(stageId) => {
                const stage = recruitmentStages.find((candidate) => candidate.id === stageId);
                updateQuery({ ...query, recruitmentStatuses: stage?.statuses ?? [] });
              }}
              onSearchChange={setSearchInput}
              onSortChange={(sort) => updateQuery({ ...query, sort })}
              onViewModeChange={setViewMode}
              preparationState={query.stages?.[0]}
              preset={query.preset ?? "all"}
              presetCounts={page.preset_counts}
              recruitmentStage={selectedStage(query.recruitmentStatuses)}
              recruitmentStageCounts={recruitmentStageCounts}
              resultSummary={
                page.matched === page.total ? `${page.total} מועמדויות` : `${page.matched} מתוך ${page.total} מועמדויות`
              }
              search={searchInput}
              sort={query.sort ?? "updated"}
              stageCounts={page.stage_counts}
              viewMode={viewMode}
            />
            <ApplicationListResults
              fetching={listQuery.isFetching && !listQuery.isPending}
              items={items}
              matchedCount={page.matched}
              offset={query.offset ?? 0}
              onClearFilters={clearFilters}
              onOffsetChange={(offset) => updateQuery({ ...query, offset }, { replace: false, resetOffset: false })}
              onRequestClose={(item) => setClosingApplicationId(item.id)}
              onRequestUpdate={(item) => setUpdatingApplicationId(item.id)}
              pageSize={PAGE_SIZE}
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
      <RecruitmentUpdateDialog application={updatingApplication} onClose={() => setUpdatingApplicationId(null)} />
    </PageShell>
  );
};
