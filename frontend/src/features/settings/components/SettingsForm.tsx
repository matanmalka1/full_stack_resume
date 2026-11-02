import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Moon, Smartphone, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { ApiProblem } from "@/api/client";
import type { Settings, UpdateSettingsRequest } from "@/api/contracts";
import { type SettingsRead, readSettings, settingsQueryKey, updateSettings } from "@/api/settings";
import { TRACK_TEMPLATE_LABEL, type TemplateName } from "@/api/templates";
import { useDisplaySettingsPreview } from "./DisplaySettingsPreview";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { useAppForm } from "@/hooks/useAppForm";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { cx } from "@/ui/cx";
import { SegmentedControl } from "@/ui/SegmentedControl";
import { showToast } from "@/ui/toast";
import { SettingsConflict } from "./SettingsConflict";
import {
  SettingsGroup,
  SettingsNoteRow,
  SettingsSection,
  SettingsSelectRow,
  SettingsSwitchRow,
} from "./SettingsSection";
import { editableSettings, reasoningEffortLabels, themeLabels } from "../settings.model";

/* The device mark is a phone's own: a wide screen's segments are words alone. */
const themeOptions = [
  { icon: Sun, label: themeLabels.light, value: "light" },
  { icon: Moon, label: themeLabels.dark, value: "dark" },
  { icon: Smartphone, label: themeLabels.system, value: "system" },
] as const satisfies readonly { icon: typeof Sun; label: string; value: Settings["ui_theme"] }[];

interface SettingsFormProps {
  etag: string | null;
  settings: Settings;
}

/* The areas of Settings the server keeps - display, the CV's defaults, AI - as one form
   with one save. A change shows at once (the display preview) and is kept only when
   saved, so the save row appears only while something is unsaved: with nothing to save
   the screen is the design's plain list of settings. */
export const SettingsForm = ({ etag, settings }: SettingsFormProps) => {
  const queryClient = useQueryClient();
  const setDisplayPreview = useDisplaySettingsPreview();
  const [baseline, setBaseline] = useState<SettingsRead>({ etag, settings });
  const [conflict, setConflict] = useState<{ base: UpdateSettingsRequest; local: UpdateSettingsRequest } | null>(null);
  const [latest, setLatest] = useState<SettingsRead | null>(null);
  const values = editableSettings(baseline.settings);
  const {
    formState: { isDirty },
    handleSubmit,
    register,
    reset,
    setValue,
    watch,
  } = useAppForm<UpdateSettingsRequest>({
    defaultValues: values,
  });
  const form = watch();
  useEffect(() => {
    setDisplayPreview({ ui_density: form.ui_density, ui_text_size: form.ui_text_size, ui_theme: form.ui_theme });
    return () => setDisplayPreview(null);
  }, [form.ui_density, form.ui_text_size, form.ui_theme, setDisplayPreview]);
  const save = useMutation({
    mutationFn: async (fields: UpdateSettingsRequest) => {
      if (baseline.etag === null) {
        throw new Error("Settings require a current ETag");
      }

      return updateSettings(fields, baseline.etag);
    },
    onError: (error, fields) => {
      if (
        error instanceof ApiProblem &&
        error.problem.code === "STATE_CONFLICT" &&
        (error.problem.status === 409 || error.problem.status === 412)
      ) {
        setConflict({ base: editableSettings(baseline.settings), local: { ...fields } });
        setLatest(null);
      }
    },
    onSuccess: (result) => {
      setBaseline(result);
      reset(editableSettings(result.settings));
      queryClient.setQueryData(settingsQueryKey, result);
      /* Settings have no other on-screen trace of a save - the save row only goes away -
         so this one command confirms. */
      showToast({ title: "ההגדרות נשמרו" });
    },
  });
  const refresh = useMutation({
    mutationFn: async () => {
      const result = await readSettings();
      if (result.etag === null) throw new Error("Settings require a current ETag");
      return result;
    },
    onSuccess: (result) => {
      setLatest(result);
      queryClient.setQueryData(settingsQueryKey, result);
    },
  });
  useEffect(() => {
    // Cache refreshes can update a pristine form; dirty forms retain their own
    // baseline and ETag until an explicit resolution or successful save.
    if (!isDirty && conflict === null && !save.isPending) {
      reset(editableSettings(settings));
    }
  }, [settings, isDirty, conflict, save.isPending, reset]);
  // Track a new read only while pristine. The guarded render update keeps
  // React state aligned with changed props without a second effect render.
  if (!isDirty && conflict === null && !save.isPending && (baseline.etag !== etag || baseline.settings !== settings)) {
    setBaseline({ etag, settings });
  }
  const resolve = (result: SettingsRead, fields: UpdateSettingsRequest) => {
    setBaseline(result);
    reset(editableSettings(result.settings));
    for (const key of Object.keys(fields) as (keyof UpdateSettingsRequest)[]) {
      if (fields[key] !== editableSettings(result.settings)[key]) {
        setValue(key, fields[key], { shouldDirty: true });
      }
    }
    setConflict(null);
    setLatest(null);
    save.reset();
    refresh.reset();
  };

  return (
    <>
      <form
        className="flex flex-col gap-4.5 lg:gap-6"
        onSubmit={handleSubmit((fields) => {
          if (conflict === null && !save.isPending) save.mutate(fields);
        })}
      >
        <fieldset disabled={save.isPending || conflict !== null} className="flex min-w-0 flex-col gap-4.5 lg:gap-6">
          <SettingsSection description="איך האפליקציה נראית אצלך." title="תצוגה">
            <SettingsGroup>
              {/* One choice of three, side by side. It was two switches - "follow the
                  system" and "dark", the second locked until the first was off. */}
              <div className="p-3.5 lg:p-4 [&_label]:px-1.5 lg:[&_svg]:hidden">
                <SegmentedControl
                  label="ערכת צבעים"
                  onChange={(theme) => setValue("ui_theme", theme, { shouldDirty: true })}
                  options={themeOptions}
                  value={form.ui_theme}
                />
              </div>
              <SettingsSwitchRow
                checked={form.ui_density === "compact"}
                label="תצוגה צפופה"
                onChange={(checked) =>
                  setValue("ui_density", checked ? "compact" : "comfortable", { shouldDirty: true })
                }
              />
              <SettingsSwitchRow
                checked={form.ui_text_size === "large"}
                label="טקסט גדול"
                onChange={(checked) => setValue("ui_text_size", checked ? "large" : "normal", { shouldDirty: true })}
              />
            </SettingsGroup>
          </SettingsSection>
          <SettingsSection description="ברירות מחדל למסמכים חדשים." title="קורות החיים">
            <SettingsGroup>
              {/* A new CV opens in this template; each one can still change it in the
                  editor, and a change here leaves existing CVs as they are. */}
              <SettingsSelectRow
                label="תבנית עיצוב"
                onChange={(event) =>
                  setValue(
                    "default_template",
                    event.target.value === "" ? null : (event.target.value as TemplateName),
                    { shouldDirty: true },
                  )
                }
                value={form.default_template ?? ""}
              >
                <option value="">{TRACK_TEMPLATE_LABEL}</option>
                {settings.available_templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.label}
                  </option>
                ))}
              </SettingsSelectRow>
            </SettingsGroup>
          </SettingsSection>
          <SettingsSection description="המודל שמנתח משרות ומנסח טיוטות." divided={false} title="בינה מלאכותית">
            <SettingsGroup>
              {settings.provider_configured ? null : (
                <SettingsNoteRow>לא הוגדר ספק AI בסביבת הריצה, ולכן אי אפשר לנתח משרה או ליצור טיוטה.</SettingsNoteRow>
              )}
              {/* The choice applies to every AI operation from now on; one already sent
                  keeps the model it was sent with. */}
              <SettingsSelectRow label="מודל AI" {...register("default_ai_model")}>
                {settings.available_ai_models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.label}
                    {model.recommended ? " — מומלץ" : ""}
                  </option>
                ))}
              </SettingsSelectRow>
              <SettingsSelectRow label="מאמץ חשיבה" {...register("default_reasoning_effort")}>
                <option value="low">{reasoningEffortLabels.low} — מהיר</option>
                <option value="medium">{reasoningEffortLabels.medium} — מאוזן</option>
                <option value="high">{reasoningEffortLabels.high} — איכות</option>
              </SettingsSelectRow>
              <SettingsSwitchRow
                checked={form.auto_generate_when_review_not_required}
                label="יצירת טיוטה אוטומטית כשלא נדרשת סקירה"
                onChange={(checked) =>
                  setValue("auto_generate_when_review_not_required", checked, { shouldDirty: true })
                }
              />
            </SettingsGroup>
          </SettingsSection>
        </fieldset>
        {/* Only while something is unsaved, pinned above the bottom of the screen, so a
            change made at the top of the page can be saved without scrolling to its end. */}
        {isDirty ? (
          <div
            className={cx(
              "sticky bottom-[calc(var(--cv-bottom-nav-height)+1rem)] z-(--cv-z-sticky) flex flex-wrap items-center justify-between gap-3",
              "rounded-surface border border-cv-border-strong bg-cv-surface/95 p-card-padding shadow-floating backdrop-blur-xl",
            )}
          >
            <p className="text-support font-semibold text-cv-text">יש שינויים שלא נשמרו.</p>
            <Button
              disabled={conflict !== null || baseline.etag === null}
              pending={save.isPending}
              pendingLabel="שומר…"
              size="compact"
              type="submit"
            >
              שמירת הגדרות
            </Button>
          </div>
        ) : null}
      </form>
      {conflict !== null && (
        <Callout title="ההגדרות השתנו מאז שפתחת את הטופס" tone="warning">
          <p>העריכות שלך נשמרו בטופס. יש לטעון את הגרסה העדכנית ולהשוות לפני שמירה נוספת.</p>
          <Button
            variant="secondary"
            pending={refresh.isPending}
            onClick={() => {
              setLatest(null);
              refresh.mutate();
            }}
          >
            טעינת הגרסה העדכנית להשוואה
          </Button>
          {refresh.error !== null && <ErrorCallout error={refresh.error} title="לא ניתן לטעון את הגרסה העדכנית" />}
          {latest !== null && (
            <SettingsConflict base={conflict.base} local={conflict.local} latest={latest} onResolve={resolve} />
          )}
        </Callout>
      )}
      {save.error === null || conflict !== null ? null : (
        <ErrorCallout
          error={save.error}
          fallbackDetail="השינויים נשארו בטופס. אפשר לנסות שוב."
          title="ההגדרות לא נשמרו"
        />
      )}
    </>
  );
};
