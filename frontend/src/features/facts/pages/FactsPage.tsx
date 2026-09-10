import { useState } from "react";
import { BookOpen } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { boardPath } from "@/app/boardReturn";
import { routePaths } from "@/app/routePaths";
import { Breadcrumbs } from "@/ui/Breadcrumbs";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { Disclosure } from "@/ui/Disclosure";
import { EmptyState } from "@/ui/EmptyState";
import { PageShell } from "@/ui/PageShell";
import { QueryState } from "@/ui/QueryState";
import { SectionHeader } from "@/ui/SectionHeader";
import { useFactDetail, useFactPool } from "../api/queries";
import { CreatePendingFactForm } from "../components/CreatePendingFactForm";
import { FactManagementDetail } from "../components/FactManagementDetail";
import { FactPoolFilters } from "../components/FactPoolFilters";
import { FactPoolList } from "../components/FactPoolList";
import { emptyFactFilters, filterFactEntries } from "../model/factFilters";

export const FactsPage = () => {
  const [filters, setFilters] = useState(emptyFactFilters);
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

      <Card className="bg-cv-surface p-5 shadow-surface sm:p-6">
        <SectionHeader
          actions={<span className="text-support font-semibold text-cv-text-muted">{entries.length} עובדות</span>}
          description="חיפוש לפי תוכן, מעמד, מקור או תגית."
          title="מאגר העובדות"
        />
        <div className="mt-5">
          <FactPoolFilters filters={filters} onChange={setFilters} sources={sources} tags={tags} />
        </div>
        {mutationsBlocked ? null : (
          <Disclosure className="mt-4" summary="הוספת עובדה חדשה">
            <CreatePendingFactForm
              onCreated={selectFact}
              profile={null}
              reason="created from the candidate facts page"
            />
          </Disclosure>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Card className="bg-cv-surface p-4 shadow-surface">
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

        <Card aria-live="polite" className="bg-cv-surface p-5 shadow-surface sm:p-6">
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
