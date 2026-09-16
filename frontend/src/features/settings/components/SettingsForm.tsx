import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { ApiProblem } from "@/api/client";
import type { Settings, UpdateSettingsRequest } from "@/api/contracts";
import { type SettingsRead, readSettings, settingsQueryKey, updateSettings } from "@/api/settings";
import { useDisplaySettingsPreview } from "@/app/layout/DisplaySettingsPreview";
import { briefServerFailureDetail, ErrorCallout } from "@/ui/ErrorCallout";
import { useAppForm } from "@/hooks/useAppForm";
import { ActionBar } from "@/ui/ActionBar";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Field } from "@/ui/Field";
import { FormSection } from "@/ui/FormSection";
import { LtrText } from "@/ui/LtrText";
import { Select } from "@/ui/Select";
import { Switch } from "@/ui/Switch";
import { SettingsConflict } from "./SettingsConflict";
import { editableSettings } from "../settings.model";

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
  const aiEnabled = form.ai_enabled_override ?? settings.ai_enabled;
  const aiAvailable = settings.provider_configured && aiEnabled;
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
          {!themeOnly && (
            <>
              <FormSection description="הרשאה ליצירת טיוטה חדשה בלי לחכות לאישור ידני." title="אוטומציה">
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

              <FormSection description="הפעלה ומדיניות עבור פעולות שנעזרות במודל שפה." title="בינה מלאכותית">
                <Switch
                  checked={aiEnabled}
                  description={
                    settings.provider_configured ? "מפעיל פעולות AI ידניות." : "לא הוגדר ספק AI בסביבת הריצה."
                  }
                  disabled={!settings.provider_configured}
                  onChange={(checked) => {
                    setValue("ai_enabled_override", checked, { shouldDirty: true });
                    if (!checked) {
                      setValue("default_execution_mode", "deterministic", { shouldDirty: true });
                    }
                  }}
                >
                  הפעלת AI
                </Switch>

                <div className="grid gap-4 sm:grid-cols-2">
                  <Field
                    hint="קובע את מסלול יצירת הטיוטה: דטרמיניסטי משתמש בחוקים ובשומרי הסף בלבד, ללא קריאת AI. ניתוח משרה רץ תמיד עם AI."
                    label="מצב ביצוע ברירת מחדל"
                  >
                    {(control) => (
                      <Select {...control} {...register("default_execution_mode")}>
                        <option value="deterministic">דטרמיניסטי</option>
                        <option disabled={!aiAvailable} value="ai">
                          AI
                        </option>
                      </Select>
                    )}
                  </Field>
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
                  <Field
                    className="sm:col-span-2"
                    hint="מאמץ גבוה עשוי לשפר משימות קשות, אך מגדיל זמן ועלות."
                    label="מאמץ חשיבה"
                  >
                    {(control) => (
                      <Select {...control} {...register("default_reasoning_effort")}>
                        <option value="low">נמוך — מהיר</option>
                        <option value="medium">בינוני — מאוזן</option>
                        <option value="high">גבוה — איכות</option>
                      </Select>
                    )}
                  </Field>
                </div>

                {selectedModel === undefined ? null : (
                  <Callout title="תעריפי המודל" tone="neutral">
                    <p>
                      <LtrText className="font-semibold text-cv-text">{selectedModel.label}</LtrText> — לכל מיליון
                      טוקנים: קלט <LtrText>${selectedModel.input_per_million_usd}</LtrText>, קלט שמור במטמון{" "}
                      <LtrText>${selectedModel.cached_input_per_million_usd}</LtrText>, ופלט{" "}
                      <LtrText>${selectedModel.output_per_million_usd}</LtrText>. העלות בפועל תוצג לאחר כל פעולה.
                    </p>
                    <p className="mt-2 text-support text-cv-text-muted">
                      בבקשות ארוכות במיוחד עשוי לחול תעריף מוגדל. המחירון הוא snapshot מתוארך ולא התחייבות למחיר עתידי.
                    </p>
                  </Callout>
                )}
              </FormSection>
            </>
          )}
          <FormSection description="משפיע מיד על הממשק, לכל מסך." divided={false} title="תצוגה">
            <div className="grid gap-4 sm:grid-cols-2">
              {!themeOnly && (
                <>
                  <Field label="צפיפות תצוגה">
                    {(control) => (
                      <Select {...control} {...register("ui_density")}>
                        <option value="comfortable">נוחה</option>
                        <option value="compact">צפופה</option>
                      </Select>
                    )}
                  </Field>
                  <Field label="גודל טקסט">
                    {(control) => (
                      <Select {...control} {...register("ui_text_size")}>
                        <option value="normal">רגיל</option>
                        <option value="large">גדול</option>
                      </Select>
                    )}
                  </Field>
                </>
              )}
              <Field label="ערכת נושא">
                {(control) => (
                  <Select {...control} {...register("ui_theme")}>
                    <option value="system">לפי המערכת</option>
                    <option value="light">בהירה</option>
                    <option value="dark">כהה</option>
                  </Select>
                )}
              </Field>
            </div>
          </FormSection>
        </fieldset>
        <ActionBar
          primary={
            <Button
              disabled={!isDirty || conflict !== null || baseline.etag === null}
              pending={save.isPending}
              pendingLabel="שומר…"
              type="submit"
            >
              שמירת הגדרות
            </Button>
          }
        />
      </form>
      {save.isSuccess ? (
        // role="status" is a Callout prop, not a DOM role; Callout already renders an
        // <output> for it.
        // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
        <Callout role="status" title="ההגדרות נשמרו" tone="success" />
      ) : null}
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
          {refresh.error !== null && <ErrorCallout error={refresh.error} fallbackTitle="הגרסה העדכנית לא נטענה" />}
          {latest !== null && (
            <SettingsConflict base={conflict.base} local={conflict.local} latest={latest} onResolve={resolve} />
          )}
        </Callout>
      )}
      {save.error === null || conflict !== null ? null : (
        <ErrorCallout error={save.error} fallbackDetail={briefServerFailureDetail} fallbackTitle="ההגדרות לא נשמרו" />
      )}
    </>
  );
};
