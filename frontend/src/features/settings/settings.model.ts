import type { Settings, UpdateSettingsRequest } from "@/api/contracts";

/* The PATCH contract accepts only the fields a person edits on this screen; `Settings`
   also carries server-computed fields (pricing, availability) that must never round-trip
   back as a write. Kept in one place so the form's `defaultValues` and its post-save
   `reset` can never drift out of sync with what the request actually sends. */
export const editableSettings = (settings: Settings): UpdateSettingsRequest => ({
  auto_generate_when_review_not_required: settings.auto_generate_when_review_not_required,
  ai_enabled_override: settings.ai_enabled_override,
  default_execution_mode: settings.default_execution_mode,
  default_ai_model: settings.default_ai_model,
  default_reasoning_effort: settings.default_reasoning_effort,
  ui_density: settings.ui_density,
  ui_text_size: settings.ui_text_size,
  ui_theme: settings.ui_theme,
});

export const settingsFieldLabels: Record<keyof UpdateSettingsRequest, string> = {
  auto_generate_when_review_not_required: "יצירת טיוטה אוטומטית",
  ai_enabled_override: "הפעלת AI",
  default_execution_mode: "מצב ביצוע",
  default_ai_model: "מודל AI",
  default_reasoning_effort: "מאמץ חשיבה",
  ui_density: "צפיפות תצוגה",
  ui_text_size: "גודל טקסט",
  ui_theme: "ערכת נושא",
};

export const settingValueLabel = (value: UpdateSettingsRequest[keyof UpdateSettingsRequest]): string => {
  if (value == null) return "ברירת מחדל של הסביבה";
  if (typeof value === "boolean") return value ? "פעיל" : "כבוי";
  const labels: Record<string, string> = {
    system: "לפי המערכת",
    light: "בהירה",
    dark: "כהה",
    comfortable: "נוחה",
    compact: "צפופה",
    normal: "רגיל",
    large: "גדול",
    deterministic: "דטרמיניסטי",
    ai: "AI",
    low: "נמוך",
    medium: "בינוני",
    high: "גבוה",
  };
  return labels[value] ?? value;
};
