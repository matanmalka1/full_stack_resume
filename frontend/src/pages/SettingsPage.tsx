import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import type { UpdateSettingsRequest } from "../api/contracts";
import { settingsQueryKey, settingsQueryOptions, updateSettings } from "../api/settings";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { Button } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Card } from "../ui/Card";
import { Checkbox } from "../ui/Checkbox";
import { Field } from "../ui/Field";
import { PageHeading } from "../ui/PageHeading";
import { Select } from "../ui/Select";

export const SettingsPage = () => {
  /* Settings stands outside the workflow, so it reports no stage rather than leaving the
     landmark showing whichever one the previous screen published. */
  useWorkflowStage("none");
  const queryClient = useQueryClient();
  const query = useQuery(settingsQueryOptions);
  const [form, setForm] = useState<UpdateSettingsRequest | null>(null);
  useEffect(() => {
    if (query.data !== undefined) {
      const settings = query.data.settings;
      setForm({
        auto_generate_when_review_not_required: settings.auto_generate_when_review_not_required,
        ai_enabled_override: settings.ai_enabled_override,
        default_execution_mode: settings.default_execution_mode,
        ui_density: settings.ui_density,
        ui_text_size: settings.ui_text_size,
      });
    }
  }, [query.data]);
  const save = useMutation({
    mutationFn: async () => {
      if (form === null || query.data?.etag == null) throw new Error("Settings require a current ETag");
      return updateSettings(form, query.data.etag);
    },
    onSuccess: (result) => queryClient.setQueryData(settingsQueryKey, result),
  });
  const settings = query.data?.settings;
  const aiAvailable = settings?.provider_configured === true && (form?.ai_enabled_override ?? settings.ai_enabled);

  return (
    <Card aria-labelledby="route-heading">
      <PageHeading id="route-heading" description="השינויים נשמרים באפליקציה ומשפיעים מיד על מסכי ה־Web.">הגדרות</PageHeading>
      <div className="mt-6 flex flex-col gap-6">
        {form === null ? <p className="text-body text-cv-text-muted">טוען הגדרות…</p> : (
          <form className="flex flex-col gap-6" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
            <Checkbox checked={form.auto_generate_when_review_not_required} onChange={(event) => setForm({ ...form, auto_generate_when_review_not_required: event.currentTarget.checked })}>
              יצירת טיוטה אוטומטית כשלא נדרשת סקירה
            </Checkbox>
            <Checkbox checked={form.ai_enabled_override ?? settings?.ai_enabled ?? false} disabled={!settings?.provider_configured} hint={settings?.provider_configured ? "מפעיל פעולות AI ידניות." : "לא הוגדר ספק AI בסביבת הריצה."} onChange={(event) => {
              const enabled = event.currentTarget.checked;
              setForm({ ...form, ai_enabled_override: enabled, default_execution_mode: enabled ? form.default_execution_mode : "deterministic" });
            }}>
              הפעלת AI
            </Checkbox>
            <Field label="מצב ביצוע ברירת מחדל">{(control) => (
              <Select {...control} value={form.default_execution_mode} onChange={(event) => setForm({ ...form, default_execution_mode: event.currentTarget.value as UpdateSettingsRequest["default_execution_mode"] })}>
                <option value="deterministic">דטרמיניסטי</option>
                <option disabled={!aiAvailable} value="ai">AI</option>
              </Select>
            )}</Field>
            <Field label="צפיפות תצוגה">{(control) => (
              <Select {...control} value={form.ui_density} onChange={(event) => setForm({ ...form, ui_density: event.currentTarget.value as UpdateSettingsRequest["ui_density"] })}>
                <option value="comfortable">נוחה</option><option value="compact">צפופה</option>
              </Select>
            )}</Field>
            <Field label="גודל טקסט">{(control) => (
              <Select {...control} value={form.ui_text_size} onChange={(event) => setForm({ ...form, ui_text_size: event.currentTarget.value as UpdateSettingsRequest["ui_text_size"] })}>
                <option value="normal">רגיל</option><option value="large">גדול</option>
              </Select>
            )}</Field>
            <Button disabled={save.isPending} type="submit">{save.isPending ? "שומר…" : "שמירת הגדרות"}</Button>
          </form>
        )}
        {save.isSuccess ? <Callout role="status" title="ההגדרות נשמרו" tone="success" /> : null}
        {query.error === null && save.error === null ? null : (
          <ErrorCallout
            error={save.error ?? query.error}
            fallbackDetail="הפנייה לשרת נכשלה."
            fallbackTitle="ההגדרות לא נשמרו"
          />
        )}
      </div>
    </Card>
  );
};
