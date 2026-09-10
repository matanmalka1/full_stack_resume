import { useState } from "react";
import { BookOpen, Plus } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { boardPath } from "@/app/boardReturn";
import { routePaths } from "@/app/routePaths";
import { Breadcrumbs } from "@/ui/Breadcrumbs";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { EmptyState } from "@/ui/EmptyState";
import { PageShell } from "@/ui/PageShell";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { useFactDetail, useFactPool } from "../api/queries";
import { FactCreationDialog } from "../components/FactCreationDialog";
import { FactsIntegrityCheck } from "../components/FactsIntegrityCheck";
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
  const selectedId = requestedId ?? entries[0]?.fact.fact_id ?? null;
  const detailQuery = useFactDetail(selectedId);
  const visible = filterFactEntries(entries, filters);
  const sources = [...new Set(entries.map(({ fact }) => fact.source))];
  const tags = [...new Set(entries.flatMap(({ fact }) => fact.tags))];
  const selectFact = (factId: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("fact", factId);
    setSearchParams(next);
  };

  return (
    <PageShell
      description="יצירה, אישור, קידום ושיוך של עובדות המועמד. עובדה קנונית מתוקנת באמצעות עובדה מחליפה ואינה נערכת במקום."
      measure="wide"
      navigation={<Breadcrumbs items={[{ label: "מועמדויות", to: boardPath() }, { label: "מאגר העובדות" }]} />}
      actions={
        mutationsBlocked ? undefined : (
          <Button onClick={() => setCreating(true)}>
            <Plus aria-hidden="true" className="size-icon-md shrink-0" />
            הוספת עובדה חדשה
          </Button>
        )
      }
      title={
        <span className="inline-flex items-center gap-2">
          <BookOpen aria-hidden="true" className="size-6 text-cv-accent" />
          מאגר העובדות
        </span>
      }
    >
      {poolQuery.data?.outOfSyncCount ? (
        <Callout role="alert" title="נמצאה אי־התאמה ביומן העובדות" tone="blocker">
          יש להפעיל את בדיקת התקינות שבמסך זה ולברר את הפער לפני קידום עובדות או שימוש בהן.
        </Callout>
      ) : null}

      <FactsIntegrityCheck />

      {/* The count reads under the bar rather than inside it, as it does on the board.
          Sitting in the filter row it was the one thing there with no label above it and
          no control below it, so it took a field's slot while looking like neither. */}
      <div className="flex flex-col gap-2">
        <Card className="cv-fields-compact bg-cv-surface p-3 shadow-surface sm:p-4">
          <FactPoolFilters filters={filters} onChange={setFilters} sources={sources} tags={tags} />
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

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <Card className="bg-cv-surface p-3 shadow-surface sm:p-4 lg:sticky lg:top-20 lg:self-start">
          <QueryState
            empty={!poolQuery.isPending && poolQuery.error === null && visible.length === 0}
            emptyState={
              <EmptyState>
                <p>לא נמצאו עובדות התואמות למסננים.</p>
              </EmptyState>
            }
            error={poolQuery.error}
            fallbackTitle="מאגר העובדות לא נטען"
            loading={poolQuery.isPending}
            loadingState={factPoolLoading}
          >
            <FactPoolList
              entries={visible}
              factHref={(factId) => `${routePaths.facts}?fact=${encodeURIComponent(factId)}`}
              selectedFactId={selectedId}
            />
          </QueryState>
        </Card>

        <Card
          aria-live="polite"
          className="bg-cv-surface p-4 shadow-surface sm:p-5 lg:sticky lg:top-20 lg:max-h-[calc(100dvh-6rem)] lg:self-start lg:overflow-y-auto"
        >
          <QueryState
            empty={!poolQuery.isPending && poolQuery.error === null && entries.length === 0}
            emptyState={
              <EmptyState>
                <p>יש ליצור עובדה כדי להתחיל לנהל את מאגר העובדות.</p>
              </EmptyState>
            }
            error={detailQuery.error}
            fallbackTitle="פרטי העובדה לא נטענו"
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
              />
            )}
          </QueryState>
        </Card>
      </div>
    </PageShell>
  );
};
