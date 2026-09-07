import { BookOpen, Database } from "lucide-react";

import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { EmptyState } from "@/ui/EmptyState";
import { QueryState } from "@/ui/QueryState";
import { SectionHeader } from "@/ui/SectionHeader";
import { useFactPool } from "../api/factQueries";
import { FactPoolList } from "./FactPoolList";

/* The whole stored knowledge, read-only. Its one job beyond listing is to say when the
   store and its audit log disagree: a fact whose recorded status differs from its own is
   evidence of a write that did not complete, and it must be reconciled before that fact
   is used again - so it is a blocker at the top of the list, not a quiet row marker. */
export const FactPoolBrowser = () => {
  const query = useFactPool();
  const pool = query.data;

  return (
    <Card aria-labelledby="canonical-facts-heading" className="bg-cv-surface p-5 shadow-surface sm:p-6">
      <SectionHeader
        actions={
          pool === undefined ? undefined : (
            <span className="inline-flex items-center gap-1.5 text-support font-semibold text-cv-text-muted">
              <Database aria-hidden="true" className="size-4" />
              {pool.entries.length} עובדות
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
          empty={pool !== undefined && pool.entries.length === 0}
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
          {pool === undefined ? null : (
            <>
              {pool.outOfSyncCount === 0 ? null : (
                <Callout className="mb-4" role="alert" title="מצב העובדה אינו תואם למצב האחרון ביומן" tone="blocker">
                  {pool.outOfSyncCount === 1
                    ? "עובדה אחת אינה תואמת ליומן השינויים. יש להפעיל בדיקת התאמה לפני שימוש נוסף."
                    : `${pool.outOfSyncCount} עובדות אינן תואמות ליומן השינויים. יש להפעיל בדיקת התאמה לפני שימוש נוסף.`}
                </Callout>
              )}
              <FactPoolList entries={pool.entries} />
            </>
          )}
        </QueryState>
      </div>
    </Card>
  );
};
