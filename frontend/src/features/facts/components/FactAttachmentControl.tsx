import { useState } from "react";

import type { Fact, FactAttachmentTargets } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Checkbox } from "@/ui/Checkbox";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Field } from "@/ui/Field";
import { Select } from "@/ui/Select";
import { cardClasses } from "@/ui/surface";
import { profileLabels } from "@/features/preparation";
import { useAttachFact } from "../api/mutations";
import { defaultFactSource } from "../model/factForm";
import { factSourceLabel, isCrossTrackFact } from "../model/factLabels";

interface FactAttachmentControlProps {
  fact: Fact;
  targets: FactAttachmentTargets;
}

export const FactAttachmentControl = ({ fact, targets }: FactAttachmentControlProps) => {
  const firstProfile = targets.profiles[0];
  const [profileId, setProfileId] = useState(firstProfile?.profile ?? "");
  const profile = targets.profiles.find((item) => item.profile === profileId) ?? firstProfile;
  const firstSection = profile?.sections[0];
  const [sectionId, setSectionId] = useState(firstSection?.section ?? "");
  const section = profile?.sections.find((item) => item.section === sectionId) ?? firstSection;
  const [pinned, setPinned] = useState(false);
  const [crossTrackAccepted, setCrossTrackAccepted] = useState(false);
  const attachment = useAttachFact(fact.fact_id);

  if (fact.status !== "canonical") return null;
  if (profile === undefined || section === undefined) {
    return (
      <Callout title="לא הוגדרו יעדי צירוף" tone="neutral">
        אין בפרופילים הקיימים סעיף שאליו ניתן לצרף עובדה.
      </Callout>
    );
  }

  const crossTrack = isCrossTrackFact(fact.source, defaultFactSource(profile.profile));

  return (
    /* A card like the fact's other blocks: a small heading with its guidance on the same
       line, the two selects, and the pin choice and the command sharing the row under
       them. The fields are the compact size the dialogs use. */
    <section
      aria-labelledby="fact-attachment-heading"
      className={cardClasses("cv-fields-compact flex flex-col gap-3 p-4.5")}
    >
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <h2 className="text-support font-bold text-cv-text-muted" id="fact-attachment-heading">
          שיוך לפרופיל
        </h2>
        <p className="text-support text-cv-text-muted">בחרו היכן העובדה תוכל להשתתף בבניית קורות החיים.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="פרופיל יעד">
          {(control) => (
            <Select
              {...control}
              onChange={(event) => {
                const next = targets.profiles.find((item) => item.profile === event.target.value);
                if (next === undefined) return;
                setProfileId(next.profile);
                setSectionId(next.sections[0]?.section ?? "");
                setCrossTrackAccepted(false);
              }}
              value={profile.profile}
            >
              {targets.profiles.map((item) => (
                <option key={item.profile} value={item.profile}>
                  {profileLabels[item.profile]} · {item.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label="סעיף יעד">
          {(control) => (
            <Select {...control} onChange={(event) => setSectionId(event.target.value)} value={section.section}>
              {profile.sections.map((item) => (
                <option key={item.section} value={item.section}>
                  {item.label}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      {crossTrack ? (
        <Callout title="מקור העובדה שייך למסלול קריירה אחר" tone="warning">
          <p>מקור העובדה: {factSourceLabel(fact.source)}.</p>
          <Checkbox
            checked={crossTrackAccepted}
            className="mt-2"
            onChange={(event) => setCrossTrackAccepted(event.currentTarget.checked)}
          >
            בדקתי את ההתאמה ומאשר/ת את הצירוף
          </Checkbox>
        </Callout>
      ) : null}
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        {section.attached ? (
          <p className="text-support text-cv-text-muted">
            {section.pinned ? "העובדה כבר משויכת ליעד הזה ומקובעת בסעיף." : "העובדה כבר משויכת ליעד הזה."}
          </p>
        ) : (
          <Checkbox checked={pinned} onChange={(event) => setPinned(event.currentTarget.checked)}>
            קיבוע העובדה במבחר של הסעיף
          </Checkbox>
        )}
        <Button
          className="ms-auto"
          disabled={section.attached || (crossTrack && !crossTrackAccepted)}
          onClick={() => attachment.mutate({ pin: pinned, profile: profile.profile, section: section.section })}
          pending={attachment.isPending}
          size="compact"
        >
          צירוף העובדה לסעיף
        </Button>
      </div>
      {/* No success notice: the line beside the button already turns into "already
          attached" once the targets refetch, which is the confirmation. */}
      {attachment.error === null ? null : (
        <ErrorCallout
          error={attachment.error}
          fallbackDetail="העובדה לא השתנתה. אפשר לנסות שוב."
          title="העובדה לא צורפה"
        />
      )}
    </section>
  );
};
