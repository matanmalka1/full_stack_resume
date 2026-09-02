import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { attachFact, factDetailQueryKey, factsQueryPrefix, transitionFact } from "../../api/facts";
import type { FactDetail, FactStatus } from "../../api/contracts";
import { ErrorCallout } from "../../app/ErrorCallout";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Checkbox } from "../../ui/Checkbox";
import { Field } from "../../ui/Field";
import { Select } from "../../ui/Select";
import { factStatusLabels } from "./factLabels";

interface FactHistoryActionsProps {
  detail: FactDetail;
  profile: string | null;
  sections: string[];
}

/* A.4's "מחזור חיי העובדות" panel below the outline: one selected fact's event log, and
   the two commands that move it forward - confirm/promote, and attaching it to a
   Profile section. Isolated from `FactLifecyclePanel` so this screen's own mutations and
   their error surfaces stay next to the buttons that send them rather than folded into
   one collapsed banner for the whole section. Keyed by fact id in the container, so a
   fact switch remounts it and its own local checkbox/section state starts clean rather
   than carrying an explicit confirmation over to a fact it was never given for. */
export const FactHistoryActions = ({ detail, profile, sections }: FactHistoryActionsProps) => {
  const queryClient = useQueryClient();
  const selected = detail.fact;
  const [explicitlyConfirmed, setExplicitlyConfirmed] = useState(false);
  const [section, setSection] = useState(sections[0] ?? "");
  const [pin, setPin] = useState(false);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: factsQueryPrefix });
    void queryClient.invalidateQueries({ queryKey: factDetailQueryKey(selected.fact_id) });
  };

  const transition = useMutation({
    mutationFn: (command: "confirm" | "promote") =>
      transitionFact(selected.fact_id, command, {
        confirm: true,
        reason: command === "confirm" ? "explicit Web confirmation" : "explicit Web promotion",
      }),
    onSuccess: () => {
      setExplicitlyConfirmed(false);
      refresh();
    },
  });
  const attachment = useMutation({
    mutationFn: () => {
      if (profile === null || section === "") {
        throw new Error("Attachment requires an active Profile and section");
      }
      return attachFact(selected.fact_id, { profile, section, pin });
    },
    onSuccess: refresh,
  });
  const error = transition.error ?? attachment.error;

  return (
    <div className="mt-4 flex flex-col gap-3">
      <h3 className="font-semibold text-cv-text">היסטוריית העובדה</h3>

      {error === null ? null : (
        <ErrorCallout
          error={error}
          fallbackDetail="מקור הידע לא השתנה ואפשר לנסות שוב."
          fallbackTitle="לא ניתן לעדכן את העובדה"
        />
      )}

      <ol className="flex flex-col gap-2">
        {detail.events.map((event) => (
          <li className="border-s-2 border-cv-border ps-3 text-support text-cv-text-muted" key={event.id}>
            {event.from_status == null
              ? "נוצרה כממתינה"
              : `${factStatusLabels[event.from_status as FactStatus] ?? event.from_status} ← ${factStatusLabels[event.to_status as FactStatus] ?? event.to_status}`}
            {event.reason === "" ? "" : ` · ${event.reason}`}
          </li>
        ))}
      </ol>

      {selected.status === "pending" || selected.status === "confirmed" ? (
        <div className="flex flex-col gap-3 rounded-control border border-cv-border bg-cv-surface p-4">
          <Checkbox
            checked={explicitlyConfirmed}
            onChange={(event) => setExplicitlyConfirmed(event.currentTarget.checked)}
          >
            בדקתי את תוכן העובדה והמקור ואני מאשר את שינוי המעמד
          </Checkbox>
          <Button
            disabled={!explicitlyConfirmed}
            onClick={() => transition.mutate(selected.status === "pending" ? "confirm" : "promote")}
            pending={transition.isPending}
          >
            {selected.status === "pending" ? "אישור העובדה" : "קידום למקור אמת"}
          </Button>
        </div>
      ) : null}

      {selected.status !== "canonical" ? null : profile === null || sections.length === 0 ? (
        <Callout title="אין יעד צירוף בהקשר הנוכחי" tone="neutral">
          נדרש פרופיל פעיל וסעיף בטיוטה כדי לצרף את העובדה.
        </Callout>
      ) : (
        <div className="flex flex-col gap-3 rounded-control border border-cv-border bg-cv-surface p-4">
          <Field label="סעיף בפרופיל הפעיל">
            {(control) => (
              <Select {...control} onChange={(event) => setSection(event.target.value)} value={section}>
                {sections.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Checkbox checked={pin} onChange={(event) => setPin(event.currentTarget.checked)}>
            קיבוע העובדה בתוכנית הבחירה הבאה
          </Checkbox>
          <Button onClick={() => attachment.mutate()} pending={attachment.isPending}>
            צירוף העובדה לסעיף
          </Button>
          {attachment.isSuccess ? (
            <Callout role="status" title="העובדה צורפה" tone="success">
              העובדה זמינה כעת למבחר של הסעיף בפרופיל הפעיל.
            </Callout>
          ) : null}
        </div>
      )}
    </div>
  );
};
