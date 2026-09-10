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
import { QueryState } from "@/ui/QueryState";
import { useFactDetail, useFactPool } from "../api/queries";
import { FactCreationDialog } from "../components/FactCreationDialog";
import { FactManagementDetail } from "../components/FactManagementDetail";
import { FactPoolFilters } from "../components/FactPoolFilters";
import { FactPoolList } from "../components/FactPoolList";
import { emptyFactFilters, filterFactEntries } from "../model/factFilters";

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
            <Plus aria-hidden="true" className="size-4 shrink-0" />
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
          יש להפעיל בדיקת התאמה בהגדרות לפני קידום עובדות או שימוש בהן.
        </Callout>
      ) : null}

      <Card className="cv-fields-compact bg-cv-surface p-3 shadow-surface sm:p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-0 grow">
            <FactPoolFilters filters={filters} onChange={setFilters} sources={sources} tags={tags} />
          </div>
          <span className="shrink-0 pb-2 text-support font-semibold whitespace-nowrap text-cv-text-muted">
            {visible.length === entries.length
              ? `${entries.length} עובדות`
              : `${visible.length} מתוך ${entries.length}`}
          </span>
        </div>
      </Card>

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
            loadingLabel="טוען עובדות…"
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
            loading={detailQuery.isPending && selectedId !== null}
            loadingLabel="טוען את פרטי העובדה…"
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
