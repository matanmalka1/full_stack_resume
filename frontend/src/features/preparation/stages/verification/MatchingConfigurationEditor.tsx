import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { applyAnalysisDecisions, type Classification, type ClassificationDecisions } from "@/api/analyses";
import { invalidateApplicationViews } from "@/api/applications";
import type { ApplicationDetail, Emphasis, Language, ProfileName, Track } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Dialog } from "@/ui/Dialog";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Field } from "@/ui/Field";
import { LiveRegion } from "@/ui/LiveRegion";
import { Select } from "@/ui/Select";
import { surfaceClasses } from "@/ui/surface";
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
  const replacement = createsAnalysis ? "ניתוח ובחירת עובדות חדשים" : "בחירת עובדות חדשה, בלי להחליף את הניתוח";
  if (detail.active_working_draft_id != null) {
    return `השמירה תיצור ${replacement}. הטיוטה הפעילה לא תימחק, אך לא תתאים להגדרות החדשות, ויהיה צריך להחליף אותה לפני האישור.`;
  }
  if (detail.latest_approved_revision_id != null || detail.latest_ready_revision_id != null) {
    return `השמירה תיצור ${replacement}. הגרסאות שאושרו והקבצים המוכנים לא ישתנו ויישארו זמינים בהיסטוריה; העבודה תמשיך מההגדרות החדשות.`;
  }
  return `השמירה תיצור ${replacement}. הקודמים נשמרים בהיסטוריה.`;
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

  const navigate = useNavigate();
  const [pendingHref, setPendingHref] = useState<string | null>(null);

  /* This form has no autosave: a choice sits only in `values` until "שמירת הגדרות
     ההתאמה" is pressed, so leaving the screen with `changed` true would otherwise drop it
     silently - the reader had already been told "זוהו שינויים שלא נשמרו" below, and nothing
     acted on it. `beforeunload` covers the close/refresh/external case; the click
     interceptor below catches in-app navigation the same way `DraftEditorPage` guards its
     own autosave buffer, one level up at `document` because this is a card inside the
     step rather than the step's own root. Both stand down on their own once a save
     actually lands, because `changed` is derived from the server's own `classification`
     and turns false the moment the refetched value matches what was just sent. */
  useEffect(() => {
    if (!changed) return;
    const handler = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [changed]);

  useEffect(() => {
    if (!changed || save.isPending) return;
    const handler = (event: MouseEvent) => {
      const anchor = (event.target as Element).closest("a");
      const href = anchor?.getAttribute("href");
      if (href?.startsWith("/") && !href.startsWith("//")) {
        event.preventDefault();
        setPendingHref(href);
      }
    };
    document.addEventListener("click", handler, true);
    return () => document.removeEventListener("click", handler, true);
  }, [changed, save.isPending]);

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
    <section
      aria-labelledby="matching-configuration-heading"
      className={surfaceClasses("flex flex-col gap-4 bg-cv-surface p-5")}
    >
      <div>
        <h2 className="text-body font-semibold text-cv-text" id="matching-configuration-heading">
          מסלול, פרופיל ודגשים
        </h2>
        <p className="mt-1 text-support leading-6 text-cv-text-muted">
          אלה ההגדרות שהניתוח ובחירת העובדות נשענים עליהן כרגע. רק מה שתשנה כאן יישמר.
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

      <Dialog
        footer={
          <>
            <Button onClick={() => setPendingHref(null)} variant="secondary">
              המשך בעריכה
            </Button>
            <Button
              onClick={() => {
                const href = pendingHref;
                setPendingHref(null);
                if (href !== null) navigate(href);
              }}
              variant="destructive"
            >
              יציאה בלי שמירה
            </Button>
          </>
        }
        headingId="matching-configuration-leave-heading"
        onClose={() => setPendingHref(null)}
        open={pendingHref !== null}
        title="לצאת בלי לשמור את הגדרות ההתאמה?"
      >
        <p dir="auto">השינויים במסלול, בפרופיל, בדגש או בשפת קורות החיים לא נשמרו ויאבדו אם תצא/י מהמסך עכשיו.</p>
      </Dialog>
    </section>
  );
};
