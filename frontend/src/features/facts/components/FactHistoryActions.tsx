import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { attachFact, factDetailQueryKey, factsQueryPrefix, transitionFact } from "@/api/facts";
import type { FactDetail } from "@/api/contracts";
import { ErrorCallout } from "@/app/ErrorCallout";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Checkbox } from "@/ui/Checkbox";
import { Field } from "@/ui/Field";
import { Select } from "@/ui/Select";
import { defaultFactSource } from "./FactFields";
import { FactEventHistory } from "./FactEventHistory";
import { factSourceLabel } from "./factLabels";

/* A.4's fact-lifecycle attach can reach across the whole canonical pool, including facts
   captured under a different career track's Profile than the one active on this
   application. Attaching one is not forbidden - a shared or situational fact is meant to
   cross tracks - but a track-specific fact from the other track rarely belongs, and
   nothing else on this screen names the mismatch before the write happens. */
const TRACK_NEUTRAL_SOURCES = new Set(["common.md", "situational_skills.md"]);

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
  const [crossTrackConfirmed, setCrossTrackConfirmed] = useState(false);

  const expectedSource = profile === null ? null : defaultFactSource(profile);
  const crossTrack =
    expectedSource !== null && !TRACK_NEUTRAL_SOURCES.has(selected.source) && selected.source !== expectedSource;

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

      <FactEventHistory events={detail.events} />

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
          <Checkbox
            checked={pin}
            hint="מקבילה ל'קיבוע העובדה' בהכנת קורות החיים, ולהכללת עובדה בכרטיס 'ביסוס עובדתי' בעורך הטיוטה."
            onChange={(event) => setPin(event.currentTarget.checked)}
          >
            קיבוע העובדה בתוכנית הבחירה הבאה
          </Checkbox>
          {crossTrack ? (
            <Callout title="עובדה זו נלקחה ממסלול קריירה אחר" tone="warning">
              <p>
                מקור העובדה: {factSourceLabel(selected.source)}. הצירוף עלול שלא להתאים למסלול או לדגש הפעיל. להמשיך בכל
                זאת?
              </p>
              <div className="mt-2.5">
                <Checkbox
                  checked={crossTrackConfirmed}
                  onChange={(event) => setCrossTrackConfirmed(event.currentTarget.checked)}
                >
                  מודע/ת שהעובדה שייכת למסלול אחר ומאשר/ת צירוף בכל זאת
                </Checkbox>
              </div>
            </Callout>
          ) : null}
          <Button
            disabled={crossTrack && !crossTrackConfirmed}
            onClick={() => attachment.mutate()}
            pending={attachment.isPending}
          >
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
