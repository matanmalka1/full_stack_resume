import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useEffect, useState } from "react";
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
import { Card } from "../ui/Card";
import { PageHeading } from "../ui/PageHeading";
import { ApplicationListFilters } from "./application-list/ApplicationListFilters";
import { ApplicationListPagination } from "./application-list/ApplicationListPagination";
import { ApplicationListTable } from "./application-list/ApplicationListTable";
import { CloseApplicationDialog } from "./application-list/CloseApplicationDialog";
import { PAGE_SIZE, paramsFromQuery, queryFromParams } from "./applicationListParams";
import { useDebouncedValue } from "./useDebouncedValue";

const SEARCH_DEBOUNCE_MS = 300;

export const ApplicationListPage = () => {
  const [params, setParams] = useSearchParams();
  const query = queryFromParams(params);
  const queryClient = useQueryClient();
  const [typedSearch, setTypedSearch] = useState(query.search ?? "");
  const settledSearch = useDebouncedValue(typedSearch, SEARCH_DEBOUNCE_MS);
  const [closingApplication, setClosingApplication] = useState<ApplicationListItem | null>(null);

  const listQuery = useQuery(applicationListQueryOptions(query));
  const page = listQuery.data;

  useWorkflowStage("none");

  const narrow = (next: ApplicationListQuery) =>
    setParams(paramsFromQuery({ ...next, offset: 0 }), { replace: true });

  useEffect(() => {
    if (settledSearch !== (query.search ?? "")) {
      narrow({ ...query, search: settledSearch });
    }
    // The settled value alone drives this synchronization; other query changes must not
    // rewrite the URL with an unchanged search value.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settledSearch]);

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
  const newApplication = (
    <Link className={buttonClasses("primary")} to="/applications/new">
      <Plus aria-hidden="true" className="size-4" />
      משרה חדשה
    </Link>
  );

  return (
    <Card aria-labelledby="route-heading">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b border-cv-border pb-5">
        <PageHeading description="מעקב אחר תהליכי התאמת קורות החיים למשרות." id="route-heading">
          המועמדויות
        </PageHeading>
        {newApplication}
      </div>

      {listQuery.error === null ? null : (
        <ErrorCallout
          className="mt-6"
          error={listQuery.error}
          fallbackDetail="הפנייה לשרת נכשלה. אפשר לרענן את העמוד ולנסות שוב."
          fallbackTitle="לא ניתן לטעון את המועמדויות"
        />
      )}

      {close.error === null ? null : (
        <ErrorCallout
          className="mt-6"
          error={close.error}
          fallbackDetail="המועמדות לא נסגרה. אפשר לנסות שוב."
          fallbackTitle="סגירת המועמדות נכשלה"
        />
      )}

      {page === undefined ? (
        listQuery.error === null ? (
          <p className="mt-6 text-body text-cv-text-muted">טוען את המועמדויות…</p>
        ) : null
      ) : page.total === 0 ? (
        <div className="mt-6 rounded-surface border border-dashed border-cv-border p-8 text-center">
          <p className="text-body text-cv-text">עוד לא נוצרה אף מועמדות.</p>
          <p className="mt-1 text-support text-cv-text-muted">
            מועמדות חדשה מתחילה בהדבקת מודעת המשרה.
          </p>
          <div className="mt-5 flex justify-center">{newApplication}</div>
        </div>
      ) : (
        <>
          <ApplicationListFilters
            activity={query.activity ?? "open"}
            onActivityChange={(activity) => narrow({ ...query, activity })}
            onPreparationStateChange={(stage) =>
              narrow({ ...query, stages: stage === undefined ? [] : [stage] })
            }
            onPresetChange={(preset) => narrow({ ...query, preset })}
            onRecruitmentStatusChange={(status) =>
              narrow({
                ...query,
                recruitmentStatuses: status === undefined ? [] : [status],
              })
            }
            onSearchChange={setTypedSearch}
            onSortChange={(sort) => narrow({ ...query, sort })}
            preparationState={query.stages?.[0]}
            preset={query.preset}
            recruitmentStatus={query.recruitmentStatuses?.[0]}
            search={typedSearch}
            sort={query.sort ?? "updated"}
            stageCounts={page.stage_counts}
          />

          <p aria-live="polite" className="mt-5 text-support text-cv-text-muted">
            {matched === page.total
              ? `${page.total} מועמדויות`
              : `${matched} מתוך ${page.total} מועמדויות`}
          </p>

          {items.length === 0 ? (
            <div className="mt-3 rounded-surface border border-dashed border-cv-border p-8 text-center">
              <p className="text-body text-cv-text">אין מועמדות שמתאימה לסינון.</p>
              <div className="mt-5 flex justify-center">
                <Button
                  onClick={() => {
                    setTypedSearch("");
                    setParams(new URLSearchParams(), { replace: true });
                  }}
                  variant="secondary"
                >
                  ניקוי הסינון
                </Button>
              </div>
            </div>
          ) : (
            <ApplicationListTable items={items} onRequestClose={setClosingApplication} />
          )}

          <ApplicationListPagination
            matchedCount={matched}
            offset={offset}
            onOffsetChange={(nextOffset) =>
              setParams(paramsFromQuery({ ...query, offset: nextOffset }))
            }
            pageSize={PAGE_SIZE}
            visibleCount={items.length}
          />
        </>
      )}

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
    </Card>
  );
};
