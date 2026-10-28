import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LayoutTemplate, Monitor, Moon, Palette, Sparkles, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { ApiProblem } from "@/api/client";
import type { Settings, UpdateSettingsRequest } from "@/api/contracts";
import { type SettingsRead, readSettings, settingsQueryKey, updateSettings } from "@/api/settings";
import { type SampleLanguage, templateLabel, templateSampleSrc } from "@/api/templates";
import { TemplateGallery } from "@/features/templates";
import { useDisplaySettingsPreview } from "./DisplaySettingsPreview";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { useAppForm } from "@/hooks/useAppForm";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { cx } from "@/ui/cx";
import { Disclosure } from "@/ui/Disclosure";
import { Field } from "@/ui/Field";
import { FormSection } from "@/ui/FormSection";
import { LtrText } from "@/ui/LtrText";
import { SectionHeader } from "@/ui/SectionHeader";
import { SegmentedControl } from "@/ui/SegmentedControl";
import { Select } from "@/ui/Select";
import { SuccessNotice } from "@/ui/SuccessNotice";
import { ViewSwitch } from "@/ui/ViewSwitch";
import { Switch } from "@/ui/Switch";
import { PhoneFoldRow, usePhoneFold } from "./PhoneFold";
import { SettingsConflict } from "./SettingsConflict";
import { editableSettings, reasoningEffortLabels } from "../settings.model";

/* The settings card surface, shared with the page's own account card and loading state.
   On a phone the cards are the rounded groups of a settings list. */
export const settingsCardClasses = "bg-cv-surface p-5 shadow-surface max-lg:rounded-surface max-lg:p-4 sm:p-6";

/* A wide screen lays each section out in two columns, as a desktop settings page does:
   its name and what it governs on the reader's side, its controls on a card at the far
   side, and a rule between one section and the next. The section's own card gives up its
   surface there, and the body under the header takes it. Below the breakpoint none of
   this applies and the section is the phone's card. */
export const settingsSectionClasses =
  "lg:grid lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:items-start lg:gap-x-10 lg:rounded-none lg:border-0 lg:border-b lg:border-cv-hairline lg:bg-transparent lg:p-0 lg:pb-8 lg:shadow-none";

/* The section's header in its own column: no rule under it, and no icon tile - the
   column itself sets the section apart. */
export const settingsSectionHeaderClasses = "lg:mb-0 lg:border-b-0 lg:pb-0 lg:[&>div>span]:hidden";

export const settingsSectionBodyClasses =
  "lg:col-start-2 lg:rounded-surface lg:border lg:border-cv-hairline lg:bg-cv-surface lg:p-5 lg:shadow-card";

const themeOptions = [
  { icon: Sun, label: "בהירה", value: "light" },
  { icon: Moon, label: "כהה", value: "dark" },
  { icon: Monitor, label: "לפי המערכת", value: "system" },
] as const satisfies readonly { icon: typeof Sun; label: string; value: Settings["ui_theme"] }[];

interface SettingsFormProps {
  etag: string | null;
  settings: Settings;
  themeOnly?: boolean;
}

export const SettingsForm = ({ etag, settings, themeOnly = false }: SettingsFormProps) => {
  const queryClient = useQueryClient();
  const setDisplayPreview = useDisplaySettingsPreview();
  const [baseline, setBaseline] = useState<SettingsRead>({ etag, settings });
  const [conflict, setConflict] = useState<{ base: UpdateSettingsRequest; local: UpdateSettingsRequest } | null>(null);
  const [latest, setLatest] = useState<SettingsRead | null>(null);
  const [sampleLanguage, setSampleLanguage] = useState<SampleLanguage>("en");
  const templateFold = usePhoneFold();
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
  const selectedModel = settings.available_ai_models.find((model) => model.id === form.default_ai_model);

  return (
    <>
      <form
        className="flex flex-col gap-6"
        onSubmit={handleSubmit((fields) => {
          if (conflict === null && !save.isPending) save.mutate(fields);
        })}
      >
        <fieldset disabled={save.isPending || conflict !== null} className="flex min-w-0 flex-col gap-6">
          {/* The cards stand in the order a person reaches for them - the look of the
              interface, then the CV's, then the AI - so the display card leads. */}
          {!themeOnly && (
            <Card className={cx(settingsCardClasses, settingsSectionClasses, "order-3")}>
              <SectionHeader
                className={cx("mb-5", settingsSectionHeaderClasses)}
                description="איך ומתי המערכת נעזרת במודל שפה."
                icon={Sparkles}
                title="בינה מלאכותית"
              />
              <div className={cx("flex flex-col gap-6", settingsSectionBodyClasses)}>
                <FormSection title="מודל">
                  <p className="text-support leading-6 text-cv-text-muted">
                    {settings.provider_configured
                      ? "ניתוח משרה, יצירת טיוטה וניסוח מחדש רצים עם AI בלבד."
                      : "לא הוגדר ספק AI בסביבת הריצה, ולכן אי אפשר לנתח משרה או ליצור טיוטה."}
                  </p>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field hint="הבחירה נשמרת לכל פעולת AI חדשה; פעולה שכבר נשלחה שומרת את המודל שלה." label="מודל AI">
                      {(control) => (
                        <Select {...control} {...register("default_ai_model")}>
                          {settings.available_ai_models.map((model) => (
                            <option key={model.id} value={model.id}>
                              {model.label}
                              {model.recommended ? " — מומלץ" : ""}
                            </option>
                          ))}
                        </Select>
                      )}
                    </Field>
                    <Field hint="מאמץ גבוה עשוי לשפר משימות קשות, אך מגדיל זמן ועלות." label="מאמץ חשיבה">
                      {(control) => (
                        <Select {...control} {...register("default_reasoning_effort")}>
                          <option value="low">{reasoningEffortLabels.low} — מהיר</option>
                          <option value="medium">{reasoningEffortLabels.medium} — מאוזן</option>
                          <option value="high">{reasoningEffortLabels.high} — איכות</option>
                        </Select>
                      )}
                    </Field>
                  </div>

                  {/* The price list is reference, not a decision: folded away it no longer
                      pushes the display settings below the fold. */}
                  {selectedModel === undefined ? null : (
                    <Disclosure summary="תעריפי המודל">
                      <p>
                        <LtrText className="font-semibold text-cv-text">{selectedModel.label}</LtrText> — לכל מיליון
                        טוקנים: קלט <LtrText>${selectedModel.input_per_million_usd}</LtrText>, קלט שמור במטמון{" "}
                        <LtrText>${selectedModel.cached_input_per_million_usd}</LtrText>,{" "}
                        {selectedModel.cache_write_per_million_usd == null ? null : (
                          <>
                            כתיבה למטמון <LtrText>${selectedModel.cache_write_per_million_usd}</LtrText>,{" "}
                          </>
                        )}
                        ופלט <LtrText>${selectedModel.output_per_million_usd}</LtrText>. העלות בפועל תוצג לאחר כל פעולה.
                      </p>
                      <p className="mt-2">
                        בבקשות ארוכות במיוחד עשוי לחול תעריף מוגדל. המחירון הוא snapshot מתוארך ולא התחייבות למחיר
                        עתידי.
                      </p>
                    </Disclosure>
                  )}
                </FormSection>

                <FormSection
                  description="הרשאה ליצירת טיוטה חדשה בלי לחכות לאישור ידני."
                  divided={false}
                  title="אוטומציה"
                >
                  <Switch
                    checked={form.auto_generate_when_review_not_required}
                    description="לאחר ניתוח שאין בו החלטה ידנית, המערכת רשאית להתחיל יצירת טיוטה באופן אוטומטי."
                    onChange={(checked) =>
                      setValue("auto_generate_when_review_not_required", checked, { shouldDirty: true })
                    }
                  >
                    יצירת טיוטה אוטומטית כשלא נדרשת סקירה
                  </Switch>
                </FormSection>
              </div>
            </Card>
          )}
          {!themeOnly && (
            <Card className={cx(settingsCardClasses, settingsSectionClasses, "order-2")}>
              <SectionHeader
                className={cx("mb-5", settingsSectionHeaderClasses)}
                description="העיצוב שבו נפתחים קורות חיים חדשים. כל משרה יכולה להחליף תבנית בעורך; שינוי כאן לא משנה קורות חיים קיימים."
                icon={LayoutTemplate}
                title="תבנית קורות חיים"
              />
              <PhoneFoldRow
                {...templateFold.rowProps}
                label="תבנית עיצוב"
                value={templateLabel(settings.available_templates, form.default_template ?? null)}
              />
              <div
                className={cx(
                  "flex flex-col gap-4 max-lg:mt-3",
                  settingsSectionBodyClasses,
                  templateFold.panelProps.className,
                )}
                id={templateFold.panelProps.id}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-support text-cv-text-muted">התצוגה המקדימה מציגה קורות חיים לדוגמה.</p>
                  <ViewSwitch
                    label="שפת הדוגמה"
                    onChange={setSampleLanguage}
                    options={[
                      { label: "אנגלית", value: "en" },
                      { label: "עברית", value: "he" },
                    ]}
                    showLabels
                    value={sampleLanguage}
                  />
                </div>
                <TemplateGallery
                  name="default-template"
                  onChange={(template) => setValue("default_template", template, { shouldDirty: true })}
                  options={settings.available_templates}
                  previewSrc={(template) => templateSampleSrc(template, sampleLanguage)}
                  value={form.default_template ?? null}
                />
              </div>
            </Card>
          )}
          <Card className={cx(settingsCardClasses, settingsSectionClasses, "order-1")}>
            <SectionHeader
              className={cx("mb-5", settingsSectionHeaderClasses)}
              description="משפיע מיד על הממשק, לכל מסך. נשמר רק בלחיצה על שמירה."
              icon={Palette}
              title="תצוגה"
            />
            <div className={cx("flex flex-col gap-6", settingsSectionBodyClasses)}>
              {/* One choice of three, side by side. It was two switches - "follow the
                  system" and "dark", the second locked until the first was off. */}
              <SegmentedControl
                label="ערכת נושא"
                onChange={(theme) => setValue("ui_theme", theme, { shouldDirty: true })}
                options={themeOptions}
                value={form.ui_theme}
              />
              {!themeOnly && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <Switch
                    checked={form.ui_density === "compact"}
                    description="כשהמתג כבוי, צפיפות התצוגה נוחה."
                    onChange={(checked) =>
                      setValue("ui_density", checked ? "compact" : "comfortable", { shouldDirty: true })
                    }
                  >
                    תצוגה צפופה
                  </Switch>
                  <Switch
                    checked={form.ui_text_size === "large"}
                    description="כשהמתג כבוי, גודל הטקסט רגיל."
                    onChange={(checked) =>
                      setValue("ui_text_size", checked ? "large" : "normal", { shouldDirty: true })
                    }
                  >
                    טקסט גדול
                  </Switch>
                </div>
              )}
            </div>
          </Card>
        </fieldset>
        {/* The save row says whether there is anything to save, so a disabled button reads
            as "nothing changed" rather than as broken. With unsaved edits it pins itself
            above the bottom of the screen, so a change made at the top of the page can be
            saved without scrolling to its end. */}
        <div
          className={cx(
            "flex flex-wrap items-center justify-between gap-3 rounded-surface border p-card-padding",
            isDirty
              ? "sticky bottom-[calc(var(--cv-bottom-nav-height)+1rem)] z-(--cv-z-sticky) border-cv-border-strong bg-cv-surface/95 shadow-floating backdrop-blur-xl"
              : "border-cv-border bg-cv-surface",
          )}
        >
          <p className={cx("text-support", isDirty ? "font-semibold text-cv-text" : "text-cv-text-muted")}>
            {isDirty ? "יש שינויים שלא נשמרו." : "כל השינויים שמורים."}
          </p>
          <Button
            disabled={!isDirty || conflict !== null || baseline.etag === null}
            pending={save.isPending}
            pendingLabel="שומר…"
            size="default"
            type="submit"
          >
            שמירת הגדרות
          </Button>
        </div>
      </form>
      {/* Settings have no other on-screen trace of a save - the button only goes quiet -
          so this one command confirms. The next edit makes it old news. */}
      {save.isSuccess && !isDirty ? <SuccessNotice onDismiss={() => save.reset()} title="ההגדרות נשמרו" /> : null}
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
