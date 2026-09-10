import { Link2 } from "lucide-react";
import { useState } from "react";

import type { Fact, FactAttachmentTargets } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Checkbox } from "@/ui/Checkbox";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Field } from "@/ui/Field";
import { Select } from "@/ui/Select";
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
    <section
      aria-labelledby="fact-attachment-heading"
      className="flex flex-col gap-4 rounded-control border border-cv-border bg-cv-surface-muted p-4"
    >
      <div className="flex items-start gap-2.5">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-control bg-cv-accent-soft text-cv-accent">
          <Link2 aria-hidden="true" className="size-4" />
        </span>
        <div>
          <h3 className="text-body font-semibold text-cv-text" id="fact-attachment-heading">
            שיוך לפרופיל
          </h3>
          <p className="mt-0.5 text-support text-cv-text-muted">
            בחרו היכן העובדה תוכל להשתתף בבניית קורות החיים.
          </p>
        </div>
      </div>
      {attachment.error === null ? null : (
        <ErrorCallout
          error={attachment.error}
          fallbackDetail="מקור הידע לא השתנה ואפשר לנסות שוב."
          fallbackTitle="לא ניתן לצרף את העובדה"
        />
      )}
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
      {section.attached ? (
        <Callout title="העובדה כבר משויכת ליעד הזה" tone="neutral">
          {section.pinned ? "העובדה גם מקובעת בסעיף." : "אפשר לבחור פרופיל או סעיף אחר."}
        </Callout>
      ) : (
        <Checkbox checked={pinned} onChange={(event) => setPinned(event.currentTarget.checked)}>
          קיבוע העובדה במבחר של הסעיף
        </Checkbox>
      )}
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
      <Button
        className="self-start sm:self-end"
        disabled={section.attached || (crossTrack && !crossTrackAccepted)}
        onClick={() => attachment.mutate({ pin: pinned, profile: profile.profile, section: section.section })}
        pending={attachment.isPending}
      >
        צירוף העובדה לסעיף
      </Button>
      {attachment.isSuccess ? (
        // role="status" is a Callout prop; Callout renders a semantic <output>.
        // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
        <Callout role="status" title="העובדה צורפה" tone="success" />
      ) : null}
    </section>
  );
};
