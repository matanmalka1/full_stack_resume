import { AlertTriangle, BookOpen, Database, Tags } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import type { Fact } from "@/api/contracts";
import { factsQueryOptions } from "@/api/facts";
import { factLabel, factStatusIcons, factStatusLabels, factStatusTones } from "@/features/facts/components/factLabels";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { EmptyState } from "@/ui/EmptyState";
import { LtrText } from "@/ui/LtrText";
import { QueryState } from "@/ui/QueryState";
import { SectionHeader } from "@/ui/SectionHeader";
import { StatusBadge } from "@/ui/StatusBadge";
import { type SummaryItem, SummaryList } from "@/ui/SummaryList";

type FactListItemProps = {
  fact: Fact;
  outOfSync: boolean;
};

const FactListItem = ({ fact, outOfSync }: FactListItemProps) => {
  const label = factLabel(fact);
  const englishRendering = fact.renderings.en === label ? undefined : fact.renderings.en;

  const summaryItems: SummaryItem[] = [
    {
      term: "מזהה ומקור",
      value: (
        <span className="flex flex-wrap items-center gap-x-2">
          <LtrText mono>{fact.fact_id}</LtrText>
          <span aria-hidden="true">·</span>
          <LtrText>{fact.source}</LtrText>
        </span>
      ),
    },
    { term: "אסמכתה", value: fact.provenance },
  ];

  return (
    <li className="p-4 transition-colors hover:bg-cv-surface-muted">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-cv-text" dir="auto">
            {label}
          </p>
          {englishRendering === undefined ? null : (
            <p className="mt-1 text-support text-cv-text-muted" dir="ltr">
              {englishRendering}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {outOfSync ? (
            <span
              aria-label="מצב העובדה אינו תואם למצב האחרון ביומן"
              className="inline-flex items-center gap-1 text-cv-blocker"
              role="img"
            >
              <AlertTriangle aria-hidden="true" className="size-4" />
            </span>
          ) : null}
          <StatusBadge
            className="px-2.5 py-0.5"
            icon={factStatusIcons[fact.status]}
            tone={factStatusTones[fact.status]}
          >
            {factStatusLabels[fact.status]}
          </StatusBadge>
        </div>
      </div>

      <SummaryList className="mt-3" items={summaryItems} />

      {fact.tags.length === 0 ? null : (
        <p className="mt-3 flex flex-wrap items-center gap-1.5 text-support text-cv-text-muted">
          <Tags aria-hidden="true" className="size-3.5" />
          {fact.tags.map((tag, index) => (
            <span className="rounded-pill bg-cv-surface-sunken px-2 py-0.5" dir="auto" key={`${index}-${tag}`}>
              {tag}
            </span>
          ))}
        </p>
      )}
    </li>
  );
};

export const CanonicalFactsBrowser = () => {
  const query = useQuery(factsQueryOptions());
  const items = query.data?.items;
  const outOfSyncCount =
    items?.filter(({ fact, recorded_status: recordedStatus }) => recordedStatus !== fact.status).length ?? 0;

  return (
    <Card aria-labelledby="canonical-facts-heading" className="bg-cv-surface p-5 shadow-surface sm:p-6">
      <SectionHeader
        actions={
          items === undefined ? undefined : (
            <span className="inline-flex items-center gap-1.5 text-support font-semibold text-cv-text-muted">
              <Database aria-hidden="true" className="size-4" />
              {items.length} עובדות
            </span>
          )
        }
        description="תצוגה לקריאה בלבד של העובדות והמקור שהן נושאות."
        headingId="canonical-facts-heading"
        icon={BookOpen}
        title="מאגר העובדות"
      />

      <div className="mt-5">
        <QueryState
          empty={items === undefined || items.length === 0}
          emptyState={
            <EmptyState className="bg-cv-surface-muted">
              <p className="text-support text-cv-text-muted">אין עדיין עובדות במאגר.</p>
            </EmptyState>
          }
          error={query.error}
          fallbackDetail="לא ניתן היה לקרוא את מאגר העובדות. לא בוצע בו שינוי."
          fallbackTitle="טעינת מאגר העובדות נכשלה"
          loading={query.isPending}
          loadingLabel="טוען את מאגר העובדות…"
        >
          {items === undefined ? null : (
            <>
              {outOfSyncCount === 0 ? null : (
                <Callout
                  className="mb-4"
                  role="alert"
                  title="מצב העובדה אינו תואם למצב האחרון ביומן"
                  tone="blocker"
                >
                  {outOfSyncCount === 1
                    ? "עובדה אחת אינה תואמת ליומן השינויים. יש להפעיל בדיקת התאמה לפני שימוש נוסף."
                    : `${outOfSyncCount} עובדות אינן תואמות ליומן השינויים. יש להפעיל בדיקת התאמה לפני שימוש נוסף.`}
                </Callout>
              )}
              <ul
                aria-label="רשימת העובדות הקנוניות"
                className="max-h-[32rem] divide-y divide-cv-border overflow-y-auto rounded-control border border-cv-border focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cv-focus"
                tabIndex={0}
              >
                {items.map(({ fact, recorded_status: recordedStatus }) => (
                  <FactListItem fact={fact} key={fact.fact_id} outOfSync={recordedStatus !== fact.status} />
                ))}
              </ul>
            </>
          )}
        </QueryState>
      </div>
    </Card>
  );
};
