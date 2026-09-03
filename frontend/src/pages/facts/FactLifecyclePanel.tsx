import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { factDetailQueryOptions, factsQueryOptions } from "../../api/facts";
import { ErrorCallout } from "../../app/ErrorCallout";
import { Field } from "../../ui/Field";
import { Select } from "../../ui/Select";
import { CreatePendingFactForm } from "./CreatePendingFactForm";
import { FactHistoryActions } from "./FactHistoryActions";
import { factLabel, factStatusLabels } from "./factLabels";

export const FactLifecyclePanel = ({ profile, sections }: { profile: string | null; sections: string[] }) => {
  const factsQuery = useQuery(factsQueryOptions());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => {
    if (selectedId === null && (factsQuery.data?.items.length ?? 0) > 0) {
      setSelectedId(factsQuery.data?.items[0]?.fact.fact_id ?? null);
    }
  }, [factsQuery.data, selectedId]);
  const detailQuery = useQuery({
    ...factDetailQueryOptions(selectedId ?? ""),
    enabled: selectedId !== null,
  });
  const selected = detailQuery.data?.fact;
  const error = factsQuery.error ?? detailQuery.error;

  return (
    /* A section under a rule, not a tinted panel of tinted panels. It is also the one
       thing on the editor that is not about the draft on screen - it edits the permanent
       knowledge - so it opens closed and takes one row until asked for. */
    <section aria-labelledby="fact-lifecycle-heading" className="border-t border-cv-border pt-4">
      <h2 className="text-heading-sm font-bold text-cv-text" id="fact-lifecycle-heading">
        מחזור חיי העובדות
      </h2>
      <p className="mt-1 text-support text-cv-text-muted">
        העובדות מוצגות בהקשר של הטיוטה. יצירה וקידום כאן משנים את מקור הידע הקבוע.
      </p>
      {error === null ? null : (
        <ErrorCallout
          className="mt-4"
          error={error}
          fallbackDetail="מקור הידע לא השתנה ואפשר לנסות שוב."
          fallbackTitle="לא ניתן לטעון את מאגר העובדות"
        />
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Field label="עובדה להצגה">
          {(control) => (
            <Select
              {...control}
              onChange={(event) => setSelectedId(event.target.value || null)}
              value={selectedId ?? ""}
            >
              {(factsQuery.data?.items.length ?? 0) === 0 ? <option value="">אין עדיין עובדות</option> : null}
              {factsQuery.data?.items.map(({ fact }) => (
                <option key={fact.fact_id} value={fact.fact_id}>
                  {factLabel(fact)} · {factStatusLabels[fact.status]}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {selected === undefined ? null : (
          <div className="border-s-2 border-cv-border ps-3">
            <p className="font-semibold text-cv-text" dir="auto">
              {factLabel(selected)}
            </p>
            <p className="mt-1 text-support text-cv-text-muted">{factStatusLabels[selected.status]}</p>
            <p className="mt-2 text-support text-cv-text-muted" dir="auto">
              {selected.meaning}
            </p>
          </div>
        )}
      </div>

      {detailQuery.data === undefined ? null : (
        <FactHistoryActions
          detail={detailQuery.data}
          key={detailQuery.data.fact.fact_id}
          profile={profile}
          sections={sections}
        />
      )}

      <details className="mt-5 rounded-control border border-cv-border bg-cv-surface p-4">
        <summary className="cursor-pointer font-semibold text-cv-text">יצירת עובדה ממתינה חדשה</summary>
        <CreatePendingFactForm onCreated={setSelectedId} profile={profile} />
      </details>
    </section>
  );
};
