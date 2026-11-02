import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { routePaths } from "@/navigation/routePaths";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { EmptyState } from "@/ui/EmptyState";
import { PageShell } from "@/ui/PageShell";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { useFactDetail, useFactPool } from "../api/queries";
import { FactCreationDialog } from "../components/FactCreationDialog";
import { FactManagementDetail } from "../components/FactManagementDetail";
import { FactPoolFilters } from "../components/FactPoolFilters";
import { FactPoolList } from "../components/FactPoolList";
import { emptyFactFilters, filterFactEntries } from "../model/factFilters";

const factPoolLoading = (
  <div className="flex flex-col gap-3">
    <LiveRegion>טוען עובדות…</LiveRegion>
    {["a", "b", "c", "d", "e", "f"].map((row) => (
      <div className="flex items-center gap-3" key={row}>
        <Skeleton className="block size-9 shrink-0" />
        <span className="flex-1 space-y-1.5">
          <Skeleton className="block h-4 w-3/4" />
          <Skeleton className="block h-3 w-1/2" />
        </span>
      </div>
    ))}
  </div>
);

const factDetailLoading = (
  <div className="page-frame flex w-full flex-col gap-4 [--page-measure:65rem]">
    <LiveRegion>טוען את פרטי העובדה…</LiveRegion>
    <Skeleton className="block h-6 w-40" />
    <Skeleton className="block h-8 w-2/3" />
    <Skeleton className="block h-24 w-full" />
    <Skeleton className="block h-24 w-full" />
  </div>
);

const factHref = (factId: string): string => `${routePaths.facts}?fact=${encodeURIComponent(factId)}`;

/* The pool and one fact are two pages of one route, chosen by the address: a `fact` in
   it shows that fact, none shows the pool - at every width, as the design draws them. A
   link from anywhere else (the search palette, a draft's claim) opens the same page. */
export const FactsPage = () => {
  const [filters, setFilters] = useState(emptyFactFilters);
  const [creating, setCreating] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const poolQuery = useFactPool();
  const entries = poolQuery.data?.entries ?? [];
  const mutationsBlocked = (poolQuery.data?.outOfSyncCount ?? 0) > 0;
  const requestedId = searchParams.get("fact");
  const requestedEventId = searchParams.get("event");
  const detailQuery = useFactDetail(requestedId);
  const visible = filterFactEntries(entries, filters);
  const poolEmpty = poolQuery.isSuccess && entries.length === 0;
  const sources = [...new Set(entries.map(({ fact }) => fact.source))];
  const pending = entries.filter(({ fact }) => fact.status === "pending");
  const poolHref = (() => {
    const next = new URLSearchParams(searchParams);
    next.delete("fact");
    next.delete("event");
    const query = next.toString();
    return query === "" ? routePaths.facts : `${routePaths.facts}?${query}`;
  })();

  /* Opening a fact from far down the pool would otherwise show it scrolled as far down
     as the row was. */
  useEffect(() => {
    globalThis.scrollTo?.({ top: 0 });
    /* The effect reads nothing from the fact: it runs because the open fact changed. */
    // oxlint-disable-next-line react/exhaustive-effect-dependencies
  }, [requestedId]);

  const selectFact = (factId: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("fact", factId);
    next.delete("event");
    setSearchParams(next);
  };

  const integrityAlert = poolQuery.data?.outOfSyncCount ? (
    <Callout role="alert" title="נמצאה אי־התאמה ביומן העובדות" tone="blocker">
      יש לפנות למפעיל המערכת לבדיקת התקינות לפני קידום עובדות או שימוש בהן.
    </Callout>
  ) : null;

  if (requestedId !== null) {
    return (
      <>
        {integrityAlert === null ? null : (
          <div className="page-frame mb-4 w-full [--page-measure:65rem]">{integrityAlert}</div>
        )}
        <QueryState
          error={detailQuery.error}
          errorTitle="לא ניתן לטעון את פרטי העובדה"
          loading={detailQuery.isPending}
          loadingState={factDetailLoading}
        >
          {detailQuery.data === undefined ? null : (
            <FactManagementDetail
              detail={detailQuery.data}
              mutationsBlocked={mutationsBlocked}
              onCreated={selectFact}
              onDeleted={() => void navigate(poolHref)}
              poolHref={poolHref}
              selectedEventId={requestedEventId}
            />
          )}
        </QueryState>
      </>
    );
  }

  return (
    <PageShell
      /* A phone's heading row has room for the title and one square: the command keeps
         its name for assistive tech and draws only its mark. */
      actions={
        mutationsBlocked ? undefined : (
          <Button
            className="max-lg:size-11 max-lg:rounded-control max-lg:px-0"
            onClick={() => setCreating(true)}
            size="default"
          >
            <Plus aria-hidden="true" className="size-icon-md shrink-0 max-lg:size-5" />
            <span className="max-lg:sr-only">עובדה חדשה</span>
          </Button>
        )
      }
      description={
        <>
          <span className="max-lg:hidden">מה שקורות החיים נבנים ממנו. רק עובדות שאושרו כמקור אמת נכנסות לטיוטות.</span>
          <span className="lg:hidden">מה שקורות החיים נבנים ממנו</span>
        </>
      }
      title="מאגר העובדות"
    >
      {integrityAlert}

      {mutationsBlocked ? null : (
        <FactCreationDialog
          formId="fact-creation-form"
          headingId="fact-creation-heading"
          onClose={() => setCreating(false)}
          onCreated={selectFact}
          open={creating}
          reason="created from the candidate facts page"
          submitLabel="יצירת עובדה"
          title="עובדה חדשה"
        />
      )}

      {/* An empty pool is one finding, said once - not a search bar over nothing. */}
      {poolEmpty ? (
        <EmptyState>
          <p className="text-body text-cv-text">מאגר העובדות עדיין ריק.</p>
          <p className="mt-1 text-support text-cv-text-muted">
            עובדה חדשה נוצרת במעמד ממתין, ואחר כך מקודמת למקור אמת.
          </p>
          {mutationsBlocked ? null : (
            <div className="mt-5 flex justify-center">
              <Button onClick={() => setCreating(true)} size="large">
                <Plus aria-hidden="true" className="size-icon-md shrink-0" />
                עובדה חדשה
              </Button>
            </div>
          )}
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-3.5 lg:gap-5">
          {poolQuery.isSuccess ? (
            <FactPoolFilters
              filters={filters}
              onChange={setFilters}
              pendingCount={pending.length}
              pendingHref={pending.length === 1 && pending[0] !== undefined ? factHref(pending[0].fact.fact_id) : null}
              sources={sources}
            />
          ) : null}
          <QueryState
            empty={poolQuery.isSuccess && visible.length === 0}
            emptyState={
              <EmptyState>
                <p>לא נמצאו עובדות התואמות לחיפוש.</p>
                <Button
                  className="mt-4"
                  onClick={() => setFilters(emptyFactFilters)}
                  size="compact"
                  variant="secondary"
                >
                  ניקוי הסינון
                </Button>
              </EmptyState>
            }
            error={poolQuery.error}
            errorTitle="לא ניתן לטעון את מאגר העובדות"
            loading={poolQuery.isPending}
            loadingState={factPoolLoading}
          >
            <FactPoolList entries={visible} factHref={factHref} />
          </QueryState>
        </div>
      )}
    </PageShell>
  );
};
