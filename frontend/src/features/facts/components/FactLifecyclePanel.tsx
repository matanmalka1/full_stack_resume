import { useState } from "react";

import { ErrorCallout } from "@/app/ErrorCallout";
import { Disclosure } from "@/ui/Disclosure";
import { Field } from "@/ui/Field";
import { Select } from "@/ui/Select";
import { useFactDetail, useFactPool } from "../api/factQueries";
import { factLabel, factStatusLabels } from "../model/factLabels";
import { CreatePendingFactForm } from "./CreatePendingFactForm";
import { FactAttachmentControl } from "./FactAttachmentControl";
import { FactEventHistory } from "./FactEventHistory";
import { FactPromotionControl } from "./FactPromotionControl";
import { FactStatusBadge } from "./FactStatusBadge";

interface FactLifecyclePanelProps {
  profile: string | null;
  sections: string[];
}

/* A section under a rule, not a tinted panel of tinted panels. It is also the one thing
   on the editor that is not about the draft on screen - it edits the permanent knowledge
   - so it opens closed and takes one row until asked for. */
export const FactLifecyclePanel = ({ profile, sections }: FactLifecyclePanelProps) => {
  const poolQuery = useFactPool();
  const entries = poolQuery.data?.entries ?? [];
  /* Which fact is on screen is a choice, and until one is made the first fact in the
     pool stands in. Derived rather than synchronised into state by an effect, so the
     panel shows a fact on the render the pool arrives, and an explicit choice that later
     leaves the pool falls back rather than pointing at nothing. */
  const [chosenId, setChosenId] = useState<string | null>(null);
  const selectedId =
    entries.find((entry) => entry.fact.fact_id === chosenId)?.fact.fact_id ?? entries[0]?.fact.fact_id ?? null;
  const detailQuery = useFactDetail(selectedId);
  const detail = detailQuery.data;
  const error = poolQuery.error ?? detailQuery.error;

  return (
    <section aria-labelledby="fact-lifecycle-heading" className="border-t border-cv-border pt-4">
      <h2 className="text-heading-sm font-bold text-cv-text" id="fact-lifecycle-heading">
        מחזור חיי העובדות
      </h2>
      <p className="mt-1 text-support text-cv-text-muted">
        העובדות מוצגות בהקשר של הטיוטה. יצירה וקידום כאן משנים את מקור הידע הקבוע. זהו כלי מתקדם, מחוץ לזרימת הבחירה
        הרגילה - כולל צירוף עובדות ממסלולי קריירה אחרים - ולכן כדאי להשתמש בו רק כשצריך לתקן או לקדם עובדה ספציפית.
      </p>
      {error === null ? null : (
        <ErrorCallout
          className="mt-4"
          error={error}
          fallbackDetail="מקור הידע לא השתנה ואפשר לנסות שוב."
          fallbackTitle="לא ניתן לטעון את מאגר העובדות"
        />
      )}

      <Disclosure className="mt-4" summary="פתיחת הכלי המתקדם">
        <div className="grid gap-4 lg:grid-cols-2">
          <Field label="עובדה להצגה">
            {(control) => (
              <Select
                {...control}
                onChange={(event) => setChosenId(event.target.value || null)}
                value={selectedId ?? ""}
              >
                {entries.length === 0 ? <option value="">אין עדיין עובדות</option> : null}
                {entries.map(({ fact }) => (
                  <option key={fact.fact_id} value={fact.fact_id}>
                    {factLabel(fact)} · {factStatusLabels[fact.status]}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          {detail === undefined ? null : (
            <div className="border-s-2 border-cv-border ps-3">
              <p className="font-semibold text-cv-text" dir="auto">
                {factLabel(detail.fact)}
              </p>
              <FactStatusBadge className="mt-1.5 px-2.5 py-0.5" status={detail.fact.status} />
              <p className="mt-2 text-support text-cv-text-muted" dir="auto">
                {detail.fact.meaning}
              </p>
            </div>
          )}
        </div>

        {detail === undefined ? null : (
          /* Keyed by fact id so switching facts starts the controls clean: an attestation
             given for one fact must never carry over to a fact it was not given for. */
          <div className="mt-4 flex flex-col gap-3" key={detail.fact.fact_id}>
            <h3 className="font-semibold text-cv-text">היסטוריית העובדה</h3>
            <FactEventHistory events={detail.events} />
            <FactPromotionControl fact={detail.fact} />
            <FactAttachmentControl fact={detail.fact} profile={profile} sections={sections} />
          </div>
        )}

        <details className="mt-5 rounded-control border border-cv-border bg-cv-surface p-4">
          <summary className="cursor-pointer font-semibold text-cv-text">יצירת עובדה ממתינה חדשה</summary>
          <CreatePendingFactForm onCreated={setChosenId} profile={profile} />
        </details>
      </Disclosure>
    </section>
  );
};
