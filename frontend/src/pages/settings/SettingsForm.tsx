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
import { Select } from "../../ui/Select";

interface SettingsFormProps {
  etag: string | null;
  settings: Settings;
}

const editableSettings = (settings: Settings): UpdateSettingsRequest => ({
  auto_generate_when_review_not_required: settings.auto_generate_when_review_not_required,
  ai_enabled_override: settings.ai_enabled_override,
  default_execution_mode: settings.default_execution_mode,
  ui_density: settings.ui_density,
  ui_text_size: settings.ui_text_size,
});

export const SettingsForm = ({ etag, settings }: SettingsFormProps) => {
  const queryClient = useQueryClient();
  const values = editableSettings(settings);
  const {
    handleSubmit,
    register,
    reset,
    setValue,
    watch,
  } = useAppForm<UpdateSettingsRequest>({
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
  const aiAvailable =
    settings.provider_configured && (form.ai_enabled_override ?? settings.ai_enabled);

  return (
    <>
      <form
        className="flex flex-col gap-6"
        onSubmit={handleSubmit((fields) => save.mutate(fields))}
      >
        <Checkbox
          checked={form.auto_generate_when_review_not_required}
          {...register("auto_generate_when_review_not_required")}
        >
          יצירת טיוטה אוטומטית כשלא נדרשת סקירה
        </Checkbox>
        <Checkbox
          checked={form.ai_enabled_override ?? settings.ai_enabled}
          disabled={!settings.provider_configured}
          hint={
            settings.provider_configured
              ? "מפעיל פעולות AI ידניות."
              : "לא הוגדר ספק AI בסביבת הריצה."
          }
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
        <Field label="מצב ביצוע ברירת מחדל">
          {(control) => (
            <Select {...control} {...register("default_execution_mode")}>
              <option value="deterministic">דטרמיניסטי</option>
              <option disabled={!aiAvailable} value="ai">
                AI
              </option>
            </Select>
          )}
        </Field>
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
        <ActionBar
          primary={
            <Button pending={save.isPending} pendingLabel="שומר…" type="submit">
              שמירת הגדרות
            </Button>
          }
        />
      </form>
      {save.isSuccess ? (
        <Callout role="status" title="ההגדרות נשמרו" tone="success" />
      ) : null}
      {save.error === null ? null : (
        <ErrorCallout
          error={save.error}
          fallbackDetail={briefServerFailureDetail}
          fallbackTitle="ההגדרות לא נשמרו"
        />
      )}
    </>
  );
};
