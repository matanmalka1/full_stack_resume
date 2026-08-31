import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  type ApplicationListQuery,
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
import { ApplicationListPagination } from "./application-list/ApplicationListPagination";
import { ApplicationListTable } from "./application-list/ApplicationListTable";
import { CloseApplicationDialog } from "./application-list/CloseApplicationDialog";
import { PAGE_SIZE, paramsFromQuery, queryFromParams } from "./applicationListParams";
import { useDebouncedValue } from "../hooks/useDebouncedValue";

const SEARCH_DEBOUNCE_MS = 300;

export const ApplicationListPage = () => {
  const [params, setParams] = useSearchParams();
  const query = queryFromParams(params);
  const queryClient = useQueryClient();
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
  ) =>
    setParams(paramsFromQuery(resetOffset ? { ...next, offset: 0 } : next), { replace });

  const close = useMutation({
    mutationFn: (applicationId: string) => closeApplication(applicationId),
    onSuccess: async () => {
      setClosingApplication(null);
      await queryClient.invalidateQueries({ queryKey: ["applications"] });
      await queryClient.invalidateQueries({ queryKey: ["application"] });
    },
  });

  const offset = query.offset ?? 0;
  const items = page?.items ?? [];
  const matched = page?.matched ?? 0;
  const resultsAreRefreshing = listQuery.isFetching && !listQuery.isPending;
  const newApplication = (
    <Link className={buttonClasses("primary")} to="/applications/new">
      <Plus aria-hidden="true" className="size-4" />
      משרה חדשה
    </Link>
  );

  return (
    <PageShell
      actions={newApplication}
      description="מעקב אחר תהליכי התאמת קורות החיים למשרות."
      title="המועמדויות"
      width="list"
    >
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
          <EmptyState>
            <p className="text-body text-cv-text">עוד לא נוצרה אף מועמדות.</p>
            <p className="mt-1 text-support text-cv-text-muted">
              מועמדות חדשה מתחילה בהדבקת מודעת המשרה.
            </p>
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
            <p aria-live="polite" className="text-support text-cv-text-muted">
              {matched === page.total
                ? `${page.total} מועמדויות`
                : `${matched} מתוך ${page.total} מועמדויות`}
            </p>

            {items.length === 0 ? (
              <EmptyState className="mt-3">
                <p className="text-body text-cv-text">אין מועמדות שמתאימה לסינון.</p>
                <div className="mt-5 flex justify-center">
                  <Button
                    onClick={() => updateQuery({})}
                    variant="secondary"
                  >
                    ניקוי הסינון
                  </Button>
                </div>
              </EmptyState>
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
