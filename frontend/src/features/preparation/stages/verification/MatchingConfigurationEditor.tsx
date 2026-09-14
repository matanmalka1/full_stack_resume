import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { applyAnalysisDecisions, type Classification, type ClassificationDecisions } from "@/api/analyses";
import { invalidateApplicationViews } from "@/api/applications";
import type { ApplicationDetail, Emphasis, Language, ProfileName, Track } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Disclosure } from "@/ui/Disclosure";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Field } from "@/ui/Field";
import { LiveRegion } from "@/ui/LiveRegion";
import { Select } from "@/ui/Select";
import { emphasisLabels, languageLabels, optionsFrom, profileLabels, trackLabels } from "../../model/analysisLabels";

interface MatchingValues {
  emphasis: Emphasis;
  language: Language;
  profile: ProfileName;
  track: Track;
}

const valuesFrom = (classification: Classification): MatchingValues | null =>
  classification.track === null ||
  classification.profile === null ||
  classification.emphasis === null ||
  classification.language === null
    ? null
    : {
        emphasis: classification.emphasis,
        language: classification.language,
        profile: classification.profile,
        track: classification.track,
      };

const emptySubmission = (): ClassificationDecisions => ({
  accept_incomplete_analysis: false,
  accept_low_fit: false,
  acceptance_reason: null,
  accepted_requirement_ids: [],
  emphasis_override: null,
  language_override: null,
  profile_override: null,
  track_override: null,
});

const changedSubmission = (current: MatchingValues, next: MatchingValues): ClassificationDecisions => ({
  ...emptySubmission(),
  emphasis_override: current.emphasis === next.emphasis ? null : next.emphasis,
  language_override: current.language === next.language ? null : next.language,
  profile_override: current.profile === next.profile ? null : next.profile,
  track_override: current.track === next.track ? null : next.track,
});

const consequence = (detail: ApplicationDetail, createsAnalysis: boolean): string => {
  const replacement = createsAnalysis ? "ניתוח ותוכנית בחירה חדשים" : "תוכנית בחירה חדשה, בלי להחליף את הניתוח";
  if (detail.active_working_draft_id != null) {
    return `השמירה תיצור ${replacement}. הטיוטה הפעילה לא תימחק, אך תהיה לא מעודכנת מול ההקשר החדש ותידרש החלפה מפורשת לפני המשך האישור.`;
  }
  if (detail.latest_approved_revision_id != null || detail.latest_ready_revision_id != null) {
    return `השמירה תיצור ${replacement}. הגרסאות שאושרו והקבצים המוכנים לא ישתנו ויישארו זמינים כהיסטוריה; העבודה החדשה תמשיך מהמצב שהשרת יחזיר.`;
  }
  return `השמירה תיצור ${replacement} ותפעיל את ההקשר החדש. הרשומות הקודמות נשמרות בהיסטוריה.`;
};

const ConfigurationSelect = <T extends string>({
  disabled,
  label,
  labels,
  onChange,
  value,
}: {
  disabled: boolean;
  label: string;
  labels: Record<T, string>;
  onChange: (value: T) => void;
  value: T;
}) => (
  <Field label={label}>
    {(control) => (
      <Select {...control} disabled={disabled} onChange={(event) => onChange(event.target.value as T)} value={value}>
        {optionsFrom(labels).map(([option, optionLabel]) => (
          <option key={option} value={option}>
            {optionLabel}
          </option>
        ))}
      </Select>
    )}
  </Field>
);

export const MatchingConfigurationEditor = ({
  classification,
  detail,
  onSaved,
}: {
  classification: Classification;
  detail: ApplicationDetail;
  onSaved: (result: Awaited<ReturnType<typeof applyAnalysisDecisions>>) => void;
}) => {
  const queryClient = useQueryClient();
  const current = useMemo(() => valuesFrom(classification), [classification]);
  const [values, setValues] = useState<MatchingValues | null>(current);

  const canEdit = detail.available_actions.includes("edit_matching_configuration");
  const submission = current === null || values === null ? null : changedSubmission(current, values);
  const changed =
    submission !== null &&
    (submission.track_override !== null ||
      submission.profile_override !== null ||
      submission.emphasis_override !== null ||
      submission.language_override !== null);
  const createsAnalysis =
    submission !== null &&
    (submission.track_override !== null ||
      submission.profile_override !== null ||
      submission.language_override !== null);

  const save = useMutation({
    mutationFn: async () => {
      if (!canEdit || submission === null || detail.active_analysis_id == null || !changed) {
        throw new Error("matching configuration is not available for this context");
      }
      return applyAnalysisDecisions(
        detail.active_analysis_id,
        detail.application.id,
        submission,
        detail.active_selection_plan_id ?? null,
      );
    },
    onSuccess: async (result) => {
      onSaved(result);
      await invalidateApplicationViews(queryClient, detail.application.id);
    },
  });

  const update = <K extends keyof MatchingValues>(key: K, value: MatchingValues[K]) => {
    save.reset();
    setValues((existing) => (existing === null ? existing : { ...existing, [key]: value }));
  };

  const unavailableBecauseOperation = detail.blocked_actions
    .find((blocked) => blocked.action === "edit_matching_configuration")
    ?.reasons.includes("MATCHING_CONTEXT_OPERATION_IN_PROGRESS");

  if (current === null || values === null) {
    return null;
  }

  return (
    <Disclosure summary="ערוך הגדרות התאמה">
      <section aria-labelledby="matching-configuration-heading" className="flex flex-col gap-4 pt-2">
        <div>
          <h2 className="text-support font-semibold text-cv-text" id="matching-configuration-heading">
            מסלול, פרופיל ודגשים
          </h2>
          <p className="mt-1 text-support leading-6 text-cv-text-muted">
            הערכים המוצגים הם ההקשר הפעיל. רק שדות ששונו יישלחו, והשרת יוודא שהניתוח ותוכנית הבחירה לא התחלפו מאז פתיחת
            הטופס.
          </p>
        </div>

        {unavailableBecauseOperation ? (
          <Callout title="ההגדרות נעולות בזמן שינוי ההקשר" tone="warning">
            יש להמתין לסיום ניתוח המשרה או שינוי תוכנית הבחירה, ואז לפתוח את ההגדרות המעודכנות.
          </Callout>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2">
          <ConfigurationSelect
            disabled={!canEdit || save.isPending}
            label="מסלול"
            labels={trackLabels}
            onChange={(track) => update("track", track)}
            value={values.track}
          />
          <ConfigurationSelect
            disabled={!canEdit || save.isPending}
            label="פרופיל"
            labels={profileLabels}
            onChange={(profile) => update("profile", profile)}
            value={values.profile}
          />
          <ConfigurationSelect
            disabled={!canEdit || save.isPending}
            label="דגש"
            labels={emphasisLabels}
            onChange={(emphasis) => update("emphasis", emphasis)}
            value={values.emphasis}
          />
          <ConfigurationSelect
            disabled={!canEdit || save.isPending}
            label="שפת קורות החיים"
            labels={languageLabels}
            onChange={(language) => update("language", language)}
            value={values.language}
          />
        </div>

        <p className="text-support leading-6 text-cv-text-muted">{consequence(detail, createsAnalysis)}</p>

        {changed ? (
          <p className="text-support font-medium text-cv-text">זוהו שינויים שלא נשמרו.</p>
        ) : (
          <p className="text-support text-cv-text-muted">לא בוצעו שינויים.</p>
        )}

        {save.error === null ? null : (
          <ErrorCallout
            error={save.error}
            fallbackDetail="ההגדרות לא נשמרו. ייתכן שהניתוח או תוכנית הבחירה התחלפו; הערכים שבחרת נשארו בטופס כדי שאפשר יהיה להשוות ולנסות שוב לאחר רענון."
            fallbackTitle="הגדרות ההתאמה לא נשמרו"
          />
        )}

        <LiveRegion>{save.isPending ? "שומר את הגדרות ההתאמה…" : undefined}</LiveRegion>

        <div className="flex flex-wrap gap-3">
          <Button
            disabled={!canEdit || !changed}
            pending={save.isPending}
            pendingLabel="שומר…"
            onClick={() => save.mutate()}
          >
            שמירת הגדרות ההתאמה
          </Button>
          <Button
            disabled={!changed || save.isPending}
            onClick={() => {
              save.reset();
              setValues(current);
            }}
            variant="secondary"
          >
            ביטול השינויים
          </Button>
        </div>
      </section>
    </Disclosure>
  );
};
