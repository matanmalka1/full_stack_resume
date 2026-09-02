import { BadgeCheck, BookOpen, Clock3, Database, ShieldCheck, Tags, type LucideIcon } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import type { FactStatus } from "../../api/contracts";
import { factsQueryOptions } from "../../api/facts";
import { ErrorCallout } from "../../app/ErrorCallout";
import { Card } from "../../ui/Card";
import { EmptyState } from "../../ui/EmptyState";
import { LtrText } from "../../ui/LtrText";
import { SectionHeader } from "../../ui/SectionHeader";
import { StatusBadge } from "../../ui/StatusBadge";
import type { StatusTone } from "../../ui/status";

const statusLabels: Record<FactStatus, string> = {
  pending: "ממתינה לאישור",
  confirmed: "אושרה",
  canonical: "מקור אמת",
};

const statusTones: Record<FactStatus, StatusTone> = {
  pending: "warning",
  confirmed: "progress",
  canonical: "success",
};

const statusIcons: Record<FactStatus, LucideIcon> = {
  pending: Clock3,
  confirmed: BadgeCheck,
  canonical: ShieldCheck,
};

export const CanonicalFactsBrowser = () => {
  const query = useQuery(factsQueryOptions());
  const items = query.data?.items;

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

      {query.isPending ? (
        <p className="mt-5 text-support text-cv-text-muted">טוען את מאגר העובדות…</p>
      ) : query.error !== null ? (
        <ErrorCallout
          className="mt-5"
          error={query.error}
          fallbackDetail="לא ניתן היה לקרוא את מאגר העובדות. לא בוצע בו שינוי."
          fallbackTitle="טעינת מאגר העובדות נכשלה"
        />
      ) : items === undefined || items.length === 0 ? (
        <EmptyState className="mt-5 bg-cv-surface-muted">
          <p className="text-support text-cv-text-muted">אין עדיין עובדות במאגר.</p>
        </EmptyState>
      ) : (
        <ul className="mt-4 max-h-[32rem] divide-y divide-cv-border overflow-y-auto rounded-control border border-cv-border">
          {items.map(({ fact, recorded_status: recordedStatus }) => {
            const label = fact.renderings.he ?? fact.renderings.en ?? fact.meaning;
            const auditMismatch = recordedStatus !== fact.status;

            return (
              <li className="p-4 hover:bg-cv-surface-muted" key={fact.fact_id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-cv-text" dir="auto">
                      {label}
                    </p>
                    {fact.renderings.en === undefined || fact.renderings.en === label ? null : (
                      <p className="mt-1 text-support text-cv-text-muted" dir="ltr">
                        {fact.renderings.en}
                      </p>
                    )}
                  </div>
                  <StatusBadge
                    className="shrink-0 px-2.5 py-0.5"
                    icon={statusIcons[fact.status]}
                    tone={statusTones[fact.status]}
                  >
                    {statusLabels[fact.status]}
                  </StatusBadge>
                </div>

                <dl className="mt-3 grid gap-x-5 gap-y-2 text-support sm:grid-cols-2">
                  <div>
                    <dt className="text-cv-text-muted">מזהה ומקור</dt>
                    <dd className="mt-0.5 flex flex-wrap gap-x-2 text-cv-text">
                      <LtrText mono>{fact.fact_id}</LtrText>
                      <span aria-hidden="true">·</span>
                      <LtrText>{fact.source}</LtrText>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-cv-text-muted">אסמכתה</dt>
                    <dd className="mt-0.5 text-cv-text" dir="auto">
                      {fact.provenance}
                    </dd>
                  </div>
                </dl>

                {fact.tags.length === 0 ? null : (
                  <p className="mt-3 flex flex-wrap items-center gap-1.5 text-support text-cv-text-muted">
                    <Tags aria-hidden="true" className="size-3.5" />
                    {fact.tags.map((tag, index) => (
                      <span
                        className="rounded-pill bg-cv-surface-sunken px-2 py-0.5"
                        dir="auto"
                        key={`${index}-${tag}`}
                      >
                        {tag}
                      </span>
                    ))}
                  </p>
                )}

                {auditMismatch ? (
                  <p className="mt-3 text-support font-semibold text-cv-blocker">
                    מצב העובדה אינו תואם למצב האחרון ביומן. יש להפעיל בדיקת התאמה לפני שימוש נוסף.
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
};
