import { useEffect, useState } from "react";
import { ChevronRight, Plus } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { routePaths } from "@/navigation/routePaths";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { cx } from "@/ui/cx";
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

/* The two halves of this screen wait at their own shape: a run of rows on the pool side,
   a record's heading and body on the detail side. Both used to wait as one line of muted
   text, which on a two-column screen read as two empty cards rather than as one screen
   arriving. */
const factPoolLoading = (
  <div className="flex flex-col gap-3">
    <LiveRegion>טוען עובדות…</LiveRegion>
    {["a", "b", "c", "d", "e", "f"].map((row) => (
      <div className="flex items-start gap-3" key={row}>
        <Skeleton className="block size-icon-md shrink-0" />
        <span className="flex-1 space-y-1.5">
          <Skeleton className="block h-4 w-3/4" />
          <Skeleton className="block h-3 w-1/2" />
        </span>
      </div>
    ))}
  </div>
);

const factDetailLoading = (
  <div className="flex flex-col gap-4">
    <LiveRegion>טוען את פרטי העובדה…</LiveRegion>
    <Skeleton className="block h-4 w-24" />
    <Skeleton className="block h-6 w-2/3" />
    <Skeleton className="block h-24 w-full" />
    <Skeleton className="block h-4 w-1/2" />
    <Skeleton className="block h-32 w-full" />
  </div>
);

export const FactsPage = () => {
  const [filters, setFilters] = useState(emptyFactFilters);
  const [creating, setCreating] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const poolQuery = useFactPool();
  const entries = poolQuery.data?.entries ?? [];
  const mutationsBlocked = (poolQuery.data?.outOfSyncCount ?? 0) > 0;
  const requestedId = searchParams.get("fact");
  const requestedEventId = searchParams.get("event");
  const selectedId = requestedId;
  const detailQuery = useFactDetail(selectedId);
  const visible = filterFactEntries(entries, filters);
  const poolEmpty = poolQuery.isSuccess && entries.length === 0;
  const sources = [...new Set(entries.map(({ fact }) => fact.source))];
  const tags = [...new Set(entries.flatMap(({ fact }) => fact.tags))];
  const pendingCount = entries.filter(({ fact }) => fact.status === "pending").length;
  /* The pool and the fact are two views of one screen, chosen by the address: a `fact` in
     it shows that fact, none shows the pool. That holds at every width. A wide screen used
     to draw both side by side and open the first fact unasked; the pool is a full-width
     table there now, and a record read beside a table half its width was neither. */
  const factOpen = requestedId !== null;
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
    document.scrollingElement?.scrollTo?.({ top: 0 });
    /* The effect reads nothing from the fact: it runs because the open fact changed. */
    // oxlint-disable-next-line react/exhaustive-effect-dependencies
  }, [requestedId]);
  const selectFact = (factId: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("fact", factId);
    next.delete("event");
    setSearchParams(next);
  };

  /* An open fact is the whole screen, as a record opened from a list is: the pool's
     masthead - its title, its line and its add command - belongs to the pool view, so it
     folds away, still in the document for the route heading the shell focuses. A wide
     screen leads the fact with the trail back to the pool instead; a phone has its chevron. */
  return (
    <div>
      <PageShell
        measure="wide"
        breadcrumb={factOpen ? [{ label: "מאגר העובדות", to: poolHref }, { label: "פרטי עובדה" }] : undefined}
        phoneMasthead={factOpen ? "hidden" : "visible"}
        wideMasthead={factOpen ? "hidden" : "visible"}
        /* A phone's heading row has room for the title and one square: the command keeps
         its name for assistive tech and draws only its mark, and the description gives way
         to one line, so the two still stand side by side. */
        actions={
          mutationsBlocked ? undefined : (
            <Button className="max-lg:size-11 max-lg:rounded-surface max-lg:px-0" onClick={() => setCreating(true)}>
              <Plus aria-hidden="true" className="size-icon-md shrink-0 max-lg:size-icon-lg" />
              <span className="max-lg:sr-only">הוספת עובדה חדשה</span>
            </Button>
          )
        }
        description={
          <>
            <span className="max-lg:hidden">
              מה שקורות החיים נבנים ממנו. רק עובדות שאושרו נכנסות כמקור אמת לטיוטות.
            </span>
            <span className="lg:hidden">מה שקורות החיים נבנים ממנו</span>
          </>
        }
        title="מאגר העובדות"
      >
        {poolQuery.data?.outOfSyncCount ? (
          <Callout role="alert" title="נמצאה אי־התאמה ביומן העובדות" tone="blocker">
            יש לפנות למפעיל המערכת לבדיקת התקינות לפני קידום עובדות או שימוש בהן.
          </Callout>
        ) : null}

        {mutationsBlocked ? null : (
          <FactCreationDialog
            formId="fact-creation-form"
            headingId="fact-creation-heading"
            intro={
              <p className="text-support leading-6 text-cv-text-muted">
                העובדה נוצרת במעמד ממתין. אישור וקידום למקור אמת הם פעולות נפרדות על העובדה שנוצרה.
              </p>
            }
            onClose={() => setCreating(false)}
            onCreated={selectFact}
            open={creating}
            reason="created from the candidate facts page"
            submitLabel="יצירת עובדה ממתינה"
            title="הוספת עובדה חדשה"
          />
        )}

        {/* An empty pool is one finding, said once. It used to draw the filter bar, a "0"
          count, and both halves of the split - the list saying nothing matched the filters
          and the detail saying to create a fact - so an empty pool read as two different
          empty states side by side, one of them blaming filters nobody had set. */}
        {poolEmpty ? (
          <EmptyState className="bg-cv-surface">
            <p className="text-body text-cv-text">מאגר העובדות עדיין ריק.</p>
            <p className="mt-1 text-support text-cv-text-muted">
              עובדה חדשה נוצרת במעמד ממתין, ואחר כך מאושרת ומקודמת למקור אמת.
            </p>
            {mutationsBlocked ? null : (
              <div className="mt-5 flex justify-center">
                <Button onClick={() => setCreating(true)}>
                  <Plus aria-hidden="true" className="size-icon-md shrink-0" />
                  הוספת עובדה חדשה
                </Button>
              </div>
            )}
          </EmptyState>
        ) : (
          <>
            {/* The count reads under the bar rather than inside it, as it does on the board.
              Sitting in the filter row it was the one thing there with no label above it and
              no control below it, so it took a field's slot while looking like neither. */}
            <div className={cx("flex flex-col gap-2", factOpen && "hidden")}>
              {/* The bar is not a panel: its field and chips sit on the canvas. */}
              <Card className="cv-fields-compact rounded-control bg-cv-surface p-3 shadow-surface max-lg:border-0 max-lg:bg-transparent max-lg:p-0 sm:p-4 lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none">
                <FactPoolFilters
                  filters={filters}
                  onChange={setFilters}
                  pendingCount={pendingCount}
                  sources={sources}
                  tags={tags}
                />
              </Card>
              {/* Silent until there is something to count. While the read was in flight this
                said "0 עובדות" beside a skeleton of six rows - a number that was not a
                finding, next to a placeholder saying the finding was still coming. */}
              {poolQuery.isPending ? null : (
                <p aria-live="polite" className="text-support text-cv-text-muted tabular-nums">
                  {visible.length === entries.length
                    ? `${entries.length} עובדות`
                    : `${visible.length} מתוך ${entries.length}`}
                </p>
              )}
            </div>

            <div className="grid gap-4">
              <div className={cx(factOpen && "hidden")}>
                <QueryState
                  empty={!poolQuery.isPending && poolQuery.error === null && visible.length === 0}
                  emptyState={
                    <EmptyState>
                      <p>לא נמצאו עובדות התואמות למסננים.</p>
                      <Button
                        className="mt-4"
                        onClick={() => setFilters(emptyFactFilters)}
                        size="compact"
                        variant="secondary"
                      >
                        ניקוי המסננים
                      </Button>
                    </EmptyState>
                  }
                  error={poolQuery.error}
                  errorTitle="לא ניתן לטעון את מאגר העובדות"
                  loading={poolQuery.isPending}
                  loadingState={factPoolLoading}
                >
                  <FactPoolList
                    entries={visible}
                    factHref={(factId) => `${routePaths.facts}?fact=${encodeURIComponent(factId)}`}
                    selectedFactId={selectedId}
                  />
                </QueryState>
              </div>

              <Card
                aria-live="polite"
                className={cx(
                  "rounded-control bg-cv-surface p-4 shadow-surface max-lg:border-0 max-lg:bg-transparent max-lg:p-0 sm:p-5 lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none",
                  !factOpen && "hidden",
                )}
                dir="ltr"
              >
                <div dir="rtl">
                  {/* The phone's way back to the pool; a wide screen has the trail above. */}
                  <Link
                    aria-label="חזרה למאגר העובדות"
                    className="-ms-2.5 mb-2 inline-flex size-11 items-center justify-center rounded-control text-cv-text hover:bg-cv-surface-muted lg:hidden"
                    to={poolHref}
                  >
                    <ChevronRight aria-hidden="true" className="size-icon-lg" />
                  </Link>
                  <QueryState
                    error={detailQuery.error}
                    errorTitle="לא ניתן לטעון את פרטי העובדה"
                    /* Also while the pool is in flight: nothing can be selected yet, so without
                     this the detail half rendered an empty card beside the pool's skeleton and
                     the two halves of one screen waited in two different ways. */
                    loading={poolQuery.isPending || (detailQuery.isPending && selectedId !== null)}
                    loadingState={factDetailLoading}
                  >
                    {detailQuery.data === undefined ? null : (
                      <FactManagementDetail
                        detail={detailQuery.data}
                        mutationsBlocked={mutationsBlocked}
                        onCreated={selectFact}
                        selectedEventId={requestedEventId}
                      />
                    )}
                  </QueryState>
                </div>
              </Card>
            </div>
          </>
        )}
      </PageShell>
    </div>
  );
};
