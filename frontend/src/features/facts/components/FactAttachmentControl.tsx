import { useState } from "react";

import type { Fact } from "@/api/contracts";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Checkbox } from "@/ui/Checkbox";
import { Field } from "@/ui/Field";
import { Select } from "@/ui/Select";
import { useAttachFact } from "../api/mutations";
import { defaultFactSource } from "../model/factForm";
import { factSourceLabel, isCrossTrackFact } from "../model/factLabels";

interface FactAttachmentControlProps {
  fact: Fact;
  profile: string | null;
  sections: string[];
}

/* Attaching a canonical fact to a section of the active Profile, so the next selection
   plan can draw on it. Only canonical facts are attachable - anything earlier in the
   lifecycle has not been established as true yet - and the attachment needs a Profile
   and a section to land in, so the absence of either is stated rather than left as a
   dead button. */
export const FactAttachmentControl = ({ fact, profile, sections }: FactAttachmentControlProps) => {
  const [section, setSection] = useState(sections[0] ?? "");
  const [pinned, setPinned] = useState(false);
  const [crossTrackAccepted, setCrossTrackAccepted] = useState(false);
  const attachment = useAttachFact(fact.fact_id);

  if (fact.status !== "canonical") {
    return null;
  }

  if (profile === null || sections.length === 0) {
    return (
      <Callout title="אין יעד צירוף בהקשר הנוכחי" tone="neutral">
        נדרש פרופיל פעיל וסעיף בטיוטה כדי לצרף את העובדה.
      </Callout>
    );
  }

  const crossTrack = isCrossTrackFact(fact.source, defaultFactSource(profile));

  return (
    <div className="flex flex-col gap-3 rounded-control border border-cv-border bg-cv-surface p-4">
      {attachment.error === null ? null : (
        <ErrorCallout
          error={attachment.error}
          fallbackDetail="מקור הידע לא השתנה ואפשר לנסות שוב."
          fallbackTitle="לא ניתן לעדכן את העובדה"
        />
      )}
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
        checked={pinned}
        hint="מקבילה ל'קיבוע העובדה' בהכנת קורות החיים, ולהכללת עובדה בכרטיס 'ביסוס עובדתי' בעורך הטיוטה."
        onChange={(event) => setPinned(event.currentTarget.checked)}
      >
        קיבוע העובדה בתוכנית הבחירה הבאה
      </Checkbox>
      {crossTrack ? (
        <Callout title="עובדה זו נלקחה ממסלול קריירה אחר" tone="warning">
          <p>
            מקור העובדה: {factSourceLabel(fact.source)}. הצירוף עלול שלא להתאים למסלול או לדגש הפעיל. להמשיך בכל זאת?
          </p>
          <div className="mt-2.5">
            <Checkbox
              checked={crossTrackAccepted}
              onChange={(event) => setCrossTrackAccepted(event.currentTarget.checked)}
            >
              מודע/ת שהעובדה שייכת למסלול אחר ומאשר/ת צירוף בכל זאת
            </Checkbox>
          </div>
        </Callout>
      ) : null}
      <Button
        disabled={crossTrack && !crossTrackAccepted}
        onClick={() => attachment.mutate({ pin: pinned, profile, section })}
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
  );
};
