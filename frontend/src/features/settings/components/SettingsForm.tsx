import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { Settings, UpdateSettingsRequest } from "@/api/contracts";
import { settingsQueryKey, updateSettings } from "@/api/settings";
import { briefServerFailureDetail, ErrorCallout } from "@/ui/ErrorCallout";
import { useAppForm } from "@/forms/useAppForm";
import { ActionBar } from "@/ui/ActionBar";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Field } from "@/ui/Field";
import { FormSection } from "@/ui/FormSection";
import { LtrText } from "@/ui/LtrText";
import { Select } from "@/ui/Select";
import { Switch } from "@/ui/Switch";
import { editableSettings } from "../settings.model";

interface SettingsFormProps {
  etag: string | null;
  settings: Settings;
}

export const SettingsForm = ({ etag, settings }: SettingsFormProps) => {
  const queryClient = useQueryClient();
  const values = editableSettings(settings);
  const { handleSubmit, register, reset, setValue, watch } = useAppForm<UpdateSettingsRequest>({
    defaultValues: values,
    values,
  });
  const form = watch();
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
  const aiEnabled = form.ai_enabled_override ?? settings.ai_enabled;
  const aiAvailable = settings.provider_configured && aiEnabled;
  const selectedModel = settings.available_ai_models.find((model) => model.id === form.default_ai_model);

  return (
    <>
      <form className="flex flex-col gap-6" onSubmit={handleSubmit((fields) => save.mutate(fields))}>
        <FormSection description="הרשאה ליצירת טיוטה חדשה בלי לחכות לאישור ידני." title="אוטומציה">
          <Switch
            checked={form.auto_generate_when_review_not_required}
            description="לאחר ניתוח שאין בו החלטה ידנית, המערכת רשאית להתחיל יצירת טיוטה באופן אוטומטי."
            onChange={(checked) => setValue("auto_generate_when_review_not_required", checked, { shouldDirty: true })}
          >
            יצירת טיוטה אוטומטית כשלא נדרשת סקירה
          </Switch>
        </FormSection>

        <FormSection description="הפעלה ומדיניות עבור פעולות שנעזרות במודל שפה." title="בינה מלאכותית">
          <Switch
            checked={aiEnabled}
            description={settings.provider_configured ? "מפעיל פעולות AI ידניות." : "לא הוגדר ספק AI בסביבת הריצה."}
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
            <Field hint="דטרמיניסטי משתמש בחוקים ובשומרי הסף בלבד." label="מצב ביצוע ברירת מחדל">
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
                <LtrText className="font-semibold text-cv-text">{selectedModel.label}</LtrText> — לכל מיליון טוקנים: קלט{" "}
                <LtrText>${selectedModel.input_per_million_usd}</LtrText>, קלט שמור במטמון{" "}
                <LtrText>${selectedModel.cached_input_per_million_usd}</LtrText>, ופלט{" "}
                <LtrText>${selectedModel.output_per_million_usd}</LtrText>. העלות בפועל תוצג לאחר כל פעולה.
              </p>
              <p className="mt-2 text-support text-cv-text-muted">
                בבקשות ארוכות במיוחד עשוי לחול תעריף מוגדל. המחירון הוא snapshot מתוארך ולא התחייבות למחיר עתידי.
              </p>
            </Callout>
          )}
        </FormSection>

        <FormSection description="משפיע מיד על הממשק, לכל מסך." divided={false} title="תצוגה">
          <div className="grid gap-4 sm:grid-cols-2">
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
          </div>
        </FormSection>

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
