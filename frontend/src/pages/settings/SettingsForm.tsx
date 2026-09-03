import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { Settings, UpdateSettingsRequest } from "../../api/contracts";
import { settingsQueryKey, updateSettings } from "../../api/settings";
import { briefServerFailureDetail, ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { ActionBar } from "../../ui/ActionBar";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Checkbox } from "../../ui/Checkbox";
import { Field } from "../../ui/Field";
import { LtrText } from "../../ui/LtrText";
import { Select } from "../../ui/Select";

interface SettingsFormProps {
  etag: string | null;
  settings: Settings;
}

const editableSettings = (settings: Settings): UpdateSettingsRequest => ({
  auto_generate_when_review_not_required: settings.auto_generate_when_review_not_required,
  ai_enabled_override: settings.ai_enabled_override,
  default_execution_mode: settings.default_execution_mode,
  default_ai_model: settings.default_ai_model,
  default_reasoning_effort: settings.default_reasoning_effort,
  ui_density: settings.ui_density,
  ui_text_size: settings.ui_text_size,
});

export const SettingsForm = ({ etag, settings }: SettingsFormProps) => {
  const queryClient = useQueryClient();
  const values = editableSettings(settings);
  const { handleSubmit, register, reset, setValue, watch } = useAppForm<UpdateSettingsRequest>({
    defaultValues: values,
    values,
  });
  const form = watch();
  const aiOverrideRegistration = register("ai_enabled_override");
  const save = useMutation({
    mutationFn: async (fields: UpdateSettingsRequest) => {
      if (etag === null) {
        throw new Error("Settings require a current ETag");
      }

      return updateSettings(fields, etag);
    },
    onSuccess: (result) => {
      reset(editableSettings(result.settings));
      queryClient.setQueryData(settingsQueryKey, result);
    },
  });
  const aiAvailable = settings.provider_configured && (form.ai_enabled_override ?? settings.ai_enabled);
  const selectedModel = settings.available_ai_models.find((model) => model.id === form.default_ai_model);

  return (
    <>
      <form className="flex flex-col gap-5" onSubmit={handleSubmit((fields) => save.mutate(fields))}>
        <div className="flex flex-col gap-2 rounded-control bg-cv-surface-muted p-2">
          <Checkbox
            checked={form.auto_generate_when_review_not_required}
            hint="לאחר ניתוח שאין בו החלטה ידנית, המערכת רשאית להתחיל יצירת טיוטה באופן אוטומטי."
            {...register("auto_generate_when_review_not_required")}
          >
            יצירת טיוטה אוטומטית כשלא נדרשת סקירה
          </Checkbox>
          <Checkbox
            checked={form.ai_enabled_override ?? settings.ai_enabled}
            disabled={!settings.provider_configured}
            hint={settings.provider_configured ? "מפעיל פעולות AI ידניות." : "לא הוגדר ספק AI בסביבת הריצה."}
            {...aiOverrideRegistration}
            onChange={(event) => {
              void aiOverrideRegistration.onChange(event);
              const enabled = event.currentTarget.checked;

              if (!enabled) {
                setValue("default_execution_mode", "deterministic");
              }
            }}
          >
            הפעלת AI
          </Checkbox>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            className="rounded-control bg-cv-surface-muted p-3"
            hint="דטרמיניסטי משתמש בחוקים ובשומרי הסף בלבד."
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
          <Field
            className="rounded-control bg-cv-surface-muted p-3"
            hint="הבחירה נשמרת לכל פעולת AI חדשה; פעולה שכבר נשלחה שומרת את המודל שלה."
            label="מודל AI"
          >
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
            className="rounded-control bg-cv-surface-muted p-3"
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
          <Field className="rounded-control bg-cv-surface-muted p-3" label="צפיפות תצוגה">
            {(control) => (
              <Select {...control} {...register("ui_density")}>
                <option value="comfortable">נוחה</option>
                <option value="compact">צפופה</option>
              </Select>
            )}
          </Field>
          <Field className="rounded-control bg-cv-surface-muted p-3 sm:col-span-2" label="גודל טקסט">
            {(control) => (
              <Select {...control} {...register("ui_text_size")}>
                <option value="normal">רגיל</option>
                <option value="large">גדול</option>
              </Select>
            )}
          </Field>
        </div>
        {selectedModel === undefined ? null : (
          <Callout title={`תעריפי ${selectedModel.label}`} tone="neutral">
            <p>
              לכל מיליון טוקנים: קלט <LtrText>${selectedModel.input_per_million_usd}</LtrText>, קלט שמור במטמון{" "}
              <LtrText>${selectedModel.cached_input_per_million_usd}</LtrText>, ופלט{" "}
              <LtrText>${selectedModel.output_per_million_usd}</LtrText>. העלות בפועל תוצג לאחר כל פעולה.
            </p>
            <p className="mt-2 text-support text-cv-text-muted">
              בבקשות ארוכות במיוחד עשוי לחול תעריף מוגדל. המחירון הוא snapshot מתוארך ולא התחייבות למחיר עתידי.
            </p>
          </Callout>
        )}
        <ActionBar
          primary={
            <Button pending={save.isPending} pendingLabel="שומר…" type="submit">
              שמירת הגדרות
            </Button>
          }
        />
      </form>
      {save.isSuccess ? <Callout role="status" title="ההגדרות נשמרו" tone="success" /> : null}
      {save.error === null ? null : (
        <ErrorCallout error={save.error} fallbackDetail={briefServerFailureDetail} fallbackTitle="ההגדרות לא נשמרו" />
      )}
    </>
  );
};
