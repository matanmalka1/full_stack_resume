import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Kanban, LayoutGrid, Table2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import {
  type ApplicationListQuery,
  applicationListQueryOptions,
  closeApplication,
  invalidateApplicationViews,
} from "../api/applications";
import type { ApplicationListItem } from "../api/contracts";
import { setNextAction } from "../api/tracking";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { appRoutes } from "../app/appRoutes";
import { useDebouncedValue } from "../hooks/useDebouncedValue";
import { Button, buttonClasses } from "../ui/Button";
import { EmptyState } from "../ui/EmptyState";
import { QueryState } from "../ui/QueryState";
import { ViewSwitch } from "../ui/ViewSwitch";
import { ApplicationListFilters } from "./application-list/ApplicationListFilters";
import { ApplicationCardsView, ApplicationPipelineView } from "./application-list/ApplicationAlternativeViews";
import { ApplicationListPagination } from "./application-list/ApplicationListPagination";
import { ApplicationListTable } from "./application-list/ApplicationListTable";
import { CloseApplicationDialog } from "./application-list/CloseApplicationDialog";
import { DashboardHeader } from "./application-list/DashboardHeader";
import { MetricsKpiGrid } from "./application-list/MetricsKpiGrid";
import { PipelineStagesBar } from "./application-list/PipelineStagesBar";
import { QuickIntakeDialog } from "./application-list/QuickIntakeDialog";
import { QuickStatusUpdateDialog } from "./application-list/QuickStatusUpdateDialog";
import { type RecruitmentStageId, recruitmentStages, selectedStage } from "./application-list/recruitmentStages";
import { UrgentActionHub } from "./application-list/UrgentActionHub";
import { PAGE_SIZE, paramsFromQuery, queryFromParams } from "./applicationListParams";

const SEARCH_DEBOUNCE_MS = 300;
type ViewMode = "table" | "cards" | "pipeline";
const viewOptions: readonly { icon: typeof Table2; label: string; value: ViewMode }[] = [
  { icon: Table2, label: "תצוגת טבלה", value: "table" },
  { icon: LayoutGrid, label: "תצוגת כרטיסים", value: "cards" },
  { icon: Kanban, label: "תצוגת שלבי גיוס", value: "pipeline" },
];

export const ApplicationListPage = () => {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const query = queryFromParams(params);
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [quickIntakeOpen, setQuickIntakeOpen] = useState(false);
  const [updatingApplication, setUpdatingApplication] = useState<ApplicationListItem | null>(null);
  /* Typing owns a local buffer so a keystroke is never lost waiting on a URL round-trip;
     the buffer is what gets debounced, and only the settled value is written to the URL.
     The URL stays the field's source of truth for Back, Forward, and shared links - the
     sync effect below mirrors an external URL change back into the buffer. */
  const [searchInput, setSearchInput] = useState(query.search ?? "");
  const settledSearch = useDebouncedValue(searchInput, SEARCH_DEBOUNCE_MS);

  useEffect(() => {
    setSearchInput(query.search ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.search]);

  useEffect(() => {
    if (settledSearch === (query.search ?? "")) {
      return;
    }
    updateQuery({ ...query, search: settledSearch === "" ? undefined : settledSearch });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settledSearch]);

  const [closingApplication, setClosingApplication] = useState<ApplicationListItem | null>(null);

  const listQuery = useQuery(
    applicationListQueryOptions({
      ...query,
      search: settledSearch === "" ? undefined : settledSearch,
    }),
  );
  const page = listQuery.data;
  const recruitmentStageCounts = Object.fromEntries(
    recruitmentStages.map((stage) => [
      stage.id,
      page === undefined
        ? undefined
        : stage.statuses.reduce((count, status) => count + (page.recruitment_status_counts[status] ?? 0), 0),
    ]),
  ) as Partial<Record<RecruitmentStageId, number | undefined>>;

  useWorkflowStage("none");

  const updateQuery = (
    next: ApplicationListQuery,
    { resetOffset = true, replace = true }: { resetOffset?: boolean; replace?: boolean } = {},
  ) => setParams(paramsFromQuery(resetOffset ? { ...next, offset: 0 } : next), { replace });

  const close = useMutation({
    mutationFn: (applicationId: string) => closeApplication(applicationId),
    onSuccess: async (_result, applicationId) => {
      setClosingApplication(null);
      await invalidateApplicationViews(queryClient, applicationId);
    },
  });
  const clearNextAction = useMutation({
    mutationFn: (applicationId: string) => setNextAction(applicationId, { next_action: null, next_action_date: null }),
    onSuccess: async (_result, applicationId) => {
      await invalidateApplicationViews(queryClient, applicationId);
      if (updatingApplication?.id === applicationId) {
        setUpdatingApplication(null);
      }
    },
  });

  const offset = query.offset ?? 0;
  const items = page?.items ?? [];
  const matched = page?.matched ?? 0;
  const resultsAreRefreshing = listQuery.isFetching && !listQuery.isPending;
  /* Intake carries the board's narrowing in its own address bar, so its way back returns
     to this board rather than to an unfiltered one. Normalised rather than echoed: what
     travels is the question this screen is actually asking. */
  const newApplicationTo = {
    pathname: appRoutes.newApplication,
    search: paramsFromQuery(query).toString(),
  };
  const newApplication = (
    <Link className={buttonClasses("primary")} to={newApplicationTo}>
      משרה חדשה
    </Link>
  );

  return (
    <section aria-labelledby="route-heading" className="page-frame">
      <DashboardHeader
        newApplicationTo={newApplicationTo}
        onOpenQuickIntake={() => setQuickIntakeOpen(true)}
        totalCount={page?.total}
      />
      <div className="mt-6 flex flex-col gap-6">
        <MetricsKpiGrid
          activeInterviewsCount={page?.preset_counts.active_interviews}
          activePreset={query.preset ?? "all"}
          needsAttentionCount={page?.preset_counts.needs_attention}
          onSelectPreset={(preset) => updateQuery({ ...query, preset: preset === "all" ? undefined : preset })}
          readyCount={page?.preset_counts.ready_to_send}
          totalCount={page?.preset_counts.all}
        />
        <PipelineStagesBar
          counts={recruitmentStageCounts}
          filterActive={(query.recruitmentStatuses?.length ?? 0) > 0}
          onSelectStage={(stageId) => {
            const stage = recruitmentStages.find((candidate) => candidate.id === stageId);
            updateQuery({ ...query, recruitmentStatuses: stage?.statuses ?? [] });
          }}
          selectedStage={selectedStage(query.recruitmentStatuses)}
        />
        <UrgentActionHub
          clearingApplicationId={clearNextAction.isPending ? (clearNextAction.variables ?? null) : null}
          items={items}
          onClearNextAction={(application) => clearNextAction.mutate(application.id)}
          onOpenStatusDialog={setUpdatingApplication}
        />
        {clearNextAction.error === null ? null : (
          <ErrorCallout
            error={clearNextAction.error}
            fallbackDetail="התזכורת לא הוסרה. הערכים הקיימים לא השתנו."
            fallbackTitle="לא ניתן להסיר את התזכורת"
          />
        )}
        {close.error === null ? null : (
          <ErrorCallout
            error={close.error}
            fallbackDetail="המועמדות לא נסגרה. אפשר לנסות שוב."
            fallbackTitle="סגירת המועמדות נכשלה"
          />
        )}

        <QueryState
          empty={page?.total === 0}
          emptyState={
            <EmptyState className="bg-cv-surface">
              <p className="text-body text-cv-text">עוד לא נוצרה אף מועמדות.</p>
              <p className="mt-1 text-support text-cv-text-muted">מועמדות חדשה מתחילה בהדבקת מודעת המשרה.</p>
              <div className="mt-5 flex justify-center">{newApplication}</div>
            </EmptyState>
          }
          error={listQuery.error}
          fallbackTitle="לא ניתן לטעון את המועמדויות"
          loading={listQuery.isPending}
          loadingLabel="טוען את המועמדויות…"
        >
          {page === undefined ? null : (
            <>
              <ApplicationListFilters
                activity={query.activity ?? "open"}
                onActivityChange={(activity) => updateQuery({ ...query, activity })}
                onPreparationStateChange={(stage) =>
                  updateQuery({ ...query, stages: stage === undefined ? [] : [stage] })
                }
                onSearchChange={setSearchInput}
                onSortChange={(sort) => updateQuery({ ...query, sort })}
                preparationState={query.stages?.[0]}
                search={searchInput}
                sort={query.sort ?? "updated"}
                stageCounts={page.stage_counts}
              />

              <div
                aria-busy={resultsAreRefreshing || undefined}
                className={`transition-opacity ${resultsAreRefreshing ? "opacity-60" : ""}`}
              >
                {/* The count is the sheet's caption: it sits on the canvas directly above
                  the rows it counts, not inside them. */}
                <div className="mb-3 flex items-center justify-between gap-4">
                  <p aria-live="polite" className="text-support font-semibold text-cv-text-muted">
                    {matched === page.total ? `${page.total} מועמדויות` : `${matched} מתוך ${page.total} מועמדויות`}
                  </p>
                  <ViewSwitch
                    label="בחירת תצוגת מועמדויות"
                    onChange={setViewMode}
                    options={viewOptions}
                    value={viewMode}
                  />
                </div>

                {items.length === 0 ? (
                  <EmptyState className="bg-cv-surface">
                    <p className="text-body text-cv-text">אין מועמדות שמתאימה לסינון.</p>
                    <div className="mt-5 flex justify-center">
                      {/* Clearing narrows the board back to everything the reader can still
                        see from where they stand: which Applications they were looking at
                        and in what order are their view, not part of the filter that
                        matched nothing. */}
                      <Button
                        onClick={() => updateQuery({ activity: query.activity, sort: query.sort })}
                        variant="secondary"
                      >
                        ניקוי הסינון
                      </Button>
                    </div>
                  </EmptyState>
                ) : viewMode === "cards" ? (
                  <ApplicationCardsView
                    items={items}
                    onRequestClose={setClosingApplication}
                    onRequestUpdate={setUpdatingApplication}
                  />
                ) : viewMode === "pipeline" ? (
                  <ApplicationPipelineView
                    items={items}
                    onRequestClose={setClosingApplication}
                    onRequestUpdate={setUpdatingApplication}
                  />
                ) : (
                  <ApplicationListTable
                    items={items}
                    onRequestClose={setClosingApplication}
                    onRequestUpdate={setUpdatingApplication}
                  />
                )}

                <ApplicationListPagination
                  matchedCount={matched}
                  offset={offset}
                  onOffsetChange={(nextOffset) =>
                    updateQuery({ ...query, offset: nextOffset }, { replace: false, resetOffset: false })
                  }
                  pageSize={PAGE_SIZE}
                  visibleCount={items.length}
                />
              </div>
            </>
          )}
        </QueryState>

        <CloseApplicationDialog
          application={closingApplication}
          onCancel={() => setClosingApplication(null)}
          onConfirm={() => {
            if (closingApplication !== null) {
              close.mutate(closingApplication.id);
            }
          }}
          pending={close.isPending}
        />
        <QuickIntakeDialog
          onClose={() => setQuickIntakeOpen(false)}
          onCreated={(applicationId, analysisQueued, analysisProblem) => {
            setQuickIntakeOpen(false);
            void invalidateApplicationViews(queryClient);
            void navigate(appRoutes.application(applicationId), {
              state: { createdApplication: { analysisProblem, analysisQueued } },
            });
          }}
          open={quickIntakeOpen}
        />
        <QuickStatusUpdateDialog application={updatingApplication} onClose={() => setUpdatingApplication(null)} />
      </div>
    </section>
  );
};
