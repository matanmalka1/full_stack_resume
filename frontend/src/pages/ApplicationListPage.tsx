import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Kanban, LayoutGrid, Plus, Table2 } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  type ApplicationListQuery,
  applicationDetailQueryPrefix,
  applicationListQueryPrefix,
  applicationListQueryOptions,
  closeApplication,
} from "../api/applications";
import type { ApplicationListItem } from "../api/contracts";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { Button, buttonClasses } from "../ui/Button";
import { EmptyState } from "../ui/EmptyState";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { ApplicationListFilters } from "./application-list/ApplicationListFilters";
import { ApplicationCardsView, ApplicationPipelineView } from "./application-list/ApplicationAlternativeViews";
import { ApplicationListPagination } from "./application-list/ApplicationListPagination";
import { ApplicationListTable } from "./application-list/ApplicationListTable";
import { CloseApplicationDialog } from "./application-list/CloseApplicationDialog";
import { PAGE_SIZE, paramsFromQuery, queryFromParams } from "./applicationListParams";
import { useDebouncedValue } from "../hooks/useDebouncedValue";

const SEARCH_DEBOUNCE_MS = 300;
type ViewMode = "table" | "cards" | "pipeline";

const viewOptions: readonly { icon: typeof Table2; label: string; value: ViewMode }[] = [
  { icon: Table2, label: "תצוגת טבלה", value: "table" },
  { icon: LayoutGrid, label: "תצוגת כרטיסים", value: "cards" },
  { icon: Kanban, label: "תצוגת שלבי גיוס", value: "pipeline" },
];

export const ApplicationListPage = () => {
  const [params, setParams] = useSearchParams();
  const query = queryFromParams(params);
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  /* The URL is the search field's single source of truth, so Back, Forward, and shared
     links update the control without a local mirror. Only the server read is debounced. */
  const settledSearch = useDebouncedValue(query.search ?? "", SEARCH_DEBOUNCE_MS);
  const [closingApplication, setClosingApplication] = useState<ApplicationListItem | null>(null);

  const listQuery = useQuery(
    applicationListQueryOptions({
      ...query,
      search: settledSearch === "" ? undefined : settledSearch,
    }),
  );
  const page = listQuery.data;

  useWorkflowStage("none");

  const updateQuery = (
    next: ApplicationListQuery,
    { resetOffset = true, replace = true }: { resetOffset?: boolean; replace?: boolean } = {},
  ) => setParams(paramsFromQuery(resetOffset ? { ...next, offset: 0 } : next), { replace });

  const close = useMutation({
    mutationFn: (applicationId: string) => closeApplication(applicationId),
    onSuccess: async () => {
      setClosingApplication(null);
      await queryClient.invalidateQueries({ queryKey: applicationListQueryPrefix });
      await queryClient.invalidateQueries({ queryKey: applicationDetailQueryPrefix });
    },
  });

  const offset = query.offset ?? 0;
  const items = page?.items ?? [];
  const matched = page?.matched ?? 0;
  const resultsAreRefreshing = listQuery.isFetching && !listQuery.isPending;
  /* Intake carries the board's narrowing in its own address bar, so its way back returns
     to this board rather than to an unfiltered one. Normalised rather than echoed: what
     travels is the question this screen is actually asking. */
  const newApplication = (
    <Link
      className={buttonClasses("primary")}
      to={{ pathname: "/applications/new", search: paramsFromQuery(query).toString() }}
    >
      <Plus aria-hidden="true" className="size-4" />
      משרה חדשה
    </Link>
  );

  return (
    <PageShell actions={newApplication} description="מעקב אחר תהליכי התאמת קורות החיים למשרות." title="המועמדויות">
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
              onPresetChange={(preset) => updateQuery({ ...query, preset })}
              onRecruitmentStatusChange={(status) =>
                updateQuery({
                  ...query,
                  recruitmentStatuses: status === undefined ? [] : [status],
                })
              }
              onSearchChange={(search) => updateQuery({ ...query, search })}
              onSortChange={(sort) => updateQuery({ ...query, sort })}
              preparationState={query.stages?.[0]}
              preset={query.preset}
              recruitmentStatus={query.recruitmentStatuses?.[0]}
              search={query.search ?? ""}
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
                <div
                  aria-label="בחירת תצוגת מועמדויות"
                  className="inline-flex items-center rounded-control border border-cv-border bg-cv-surface-muted p-0.5"
                  role="group"
                >
                  {viewOptions.map(({ icon: Icon, label, value }) => (
                    <button
                      aria-label={label}
                      aria-pressed={viewMode === value}
                      className={`rounded-control p-2 transition-colors ${
                        viewMode === value
                          ? "bg-cv-surface text-cv-accent shadow-surface"
                          : "text-cv-text-muted hover:text-cv-text"
                      }`}
                      key={value}
                      onClick={() => setViewMode(value)}
                      title={label}
                      type="button"
                    >
                      <Icon aria-hidden="true" className="size-4" />
                    </button>
                  ))}
                </div>
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
                <ApplicationCardsView items={items} onRequestClose={setClosingApplication} />
              ) : viewMode === "pipeline" ? (
                <ApplicationPipelineView items={items} onRequestClose={setClosingApplication} />
              ) : (
                <ApplicationListTable items={items} onRequestClose={setClosingApplication} />
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
    </PageShell>
  );
};
