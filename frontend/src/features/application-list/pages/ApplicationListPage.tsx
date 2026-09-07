import { Kanban, LayoutGrid, Table2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { routePaths } from "@/app/routePaths";
import { RecruitmentUpdateDialog } from "@/features/recruitment";
import { Button, buttonClasses } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { QueryState } from "@/ui/QueryState";
import { ViewSwitch } from "@/ui/ViewSwitch";
import { ApplicationCardsView } from "../components/ApplicationCardsView";
import { ApplicationListFilters } from "../components/ApplicationListFilters";
import { ApplicationListPagination } from "../components/ApplicationListPagination";
import { ApplicationListTable } from "../components/ApplicationListTable";
import { ApplicationPipelineView } from "../components/ApplicationPipelineView";
import { CloseApplicationDialog } from "../components/CloseApplicationDialog";
import { ApplicationAttentionSummary } from "../components/ApplicationAttentionSummary";
import { ApplicationListHeader } from "../components/ApplicationListHeader";
import { ApplicationStatusSummary } from "../components/ApplicationStatusSummary";
import { useApplicationListMutations } from "../api/mutations";
import { useApplicationListQuery } from "../hooks/useApplicationListQuery";
import { PAGE_SIZE, paramsFromQuery } from "../model/applicationListParams";
import { type RecruitmentStageId, recruitmentStages, selectedStage } from "../model/recruitmentStages";

type ViewMode = "table" | "cards" | "pipeline";
const initialViewMode = (): ViewMode =>
  typeof window.matchMedia === "function" && window.matchMedia("(max-width: 639px)").matches ? "cards" : "table";

const viewOptions = [
  { icon: Table2, label: "תצוגת טבלה", value: "table" },
  { icon: LayoutGrid, label: "תצוגת כרטיסים", value: "cards" },
  { icon: Kanban, label: "תצוגת שלבי גיוס", value: "pipeline" },
] as const;

const findApplication = (items: readonly ApplicationListItem[], id: string | null) =>
  id === null ? null : (items.find((item) => item.id === id) ?? null);

export const ApplicationListPage = () => {
  const { listQuery, query, searchInput, setSearchInput, updateQuery } = useApplicationListQuery();
  const [viewMode, setViewMode] = useState<ViewMode>(initialViewMode);
  const [closingApplicationId, setClosingApplicationId] = useState<string | null>(null);
  const [updatingApplicationId, setUpdatingApplicationId] = useState<string | null>(null);
  const { clearNextActionMutation, closeMutation } = useApplicationListMutations({
    onApplicationClosed: () => setClosingApplicationId(null),
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
  const newApplicationTo = { pathname: routePaths.newApplication, search: paramsFromQuery(query).toString() };
  const newApplication = (
    <Link className={buttonClasses("primary")} to={newApplicationTo}>
      משרה חדשה
    </Link>
  );

  return (
    <section aria-labelledby="route-heading" className="page-frame">
      <ApplicationListHeader newApplicationTo={newApplicationTo} totalCount={page?.total} />
      <div className="mt-6 flex flex-col gap-6">
        <ApplicationStatusSummary
          activeInterviewsCount={page?.preset_counts.active_interviews}
          activePreset={query.preset ?? "all"}
          needsAttentionCount={page?.preset_counts.needs_attention}
          onSelectPreset={(preset) => updateQuery({ ...query, preset: preset === "all" ? undefined : preset })}
          readyCount={page?.preset_counts.ready_to_send}
          totalCount={page?.preset_counts.all}
        />
        <ApplicationAttentionSummary
          clearingApplicationId={clearNextActionMutation.isPending ? (clearNextActionMutation.variables ?? null) : null}
          items={items}
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
                onPreparationStateChange={(stage) => updateQuery({ ...query, stages: stage ? [stage] : [] })}
                onRecruitmentStageChange={(stageId) => {
                  const stage = recruitmentStages.find((candidate) => candidate.id === stageId);
                  updateQuery({ ...query, recruitmentStatuses: stage?.statuses ?? [] });
                }}
                onSearchChange={setSearchInput}
                onSortChange={(sort) => updateQuery({ ...query, sort })}
                preparationState={query.stages?.[0]}
                recruitmentStage={selectedStage(query.recruitmentStatuses)}
                recruitmentStageCounts={recruitmentStageCounts}
                search={searchInput}
                sort={query.sort ?? "updated"}
                stageCounts={page.stage_counts}
              />
              <div
                aria-busy={listQuery.isFetching && !listQuery.isPending ? true : undefined}
                className={`transition-opacity ${listQuery.isFetching && !listQuery.isPending ? "opacity-60" : ""}`}
              >
                <div className="mb-3 flex items-center justify-between gap-4">
                  <p aria-live="polite" className="text-support font-semibold text-cv-text-muted">
                    {page.matched === page.total
                      ? `${page.total} מועמדויות`
                      : `${page.matched} מתוך ${page.total} מועמדויות`}
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
                    onRequestClose={(item) => setClosingApplicationId(item.id)}
                    onRequestUpdate={(item) => setUpdatingApplicationId(item.id)}
                  />
                ) : viewMode === "pipeline" ? (
                  <ApplicationPipelineView
                    items={items}
                    onRequestUpdate={(item) => setUpdatingApplicationId(item.id)}
                  />
                ) : (
                  <ApplicationListTable
                    items={items}
                    onRequestClose={(item) => setClosingApplicationId(item.id)}
                    onRequestUpdate={(item) => setUpdatingApplicationId(item.id)}
                  />
                )}
                <ApplicationListPagination
                  matchedCount={page.matched}
                  offset={query.offset ?? 0}
                  onOffsetChange={(offset) => updateQuery({ ...query, offset }, { replace: false, resetOffset: false })}
                  pageSize={PAGE_SIZE}
                  visibleCount={items.length}
                />
              </div>
            </>
          )}
        </QueryState>
      </div>
      <CloseApplicationDialog
        application={closingApplication}
        onCancel={() => setClosingApplicationId(null)}
        onConfirm={() => closingApplicationId && closeMutation.mutate(closingApplicationId)}
        pending={closeMutation.isPending}
      />
      <RecruitmentUpdateDialog application={updatingApplication} onClose={() => setUpdatingApplicationId(null)} />
    </section>
  );
};
