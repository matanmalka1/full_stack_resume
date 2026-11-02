import type { Settings } from "./contracts";

/* The render templates a CV can choose (backend `cv_engine/domain/templates.py`). The
   catalog arrives with the settings read; nothing here duplicates it. */
export type TemplateOption = Settings["available_templates"][number];
export type TemplateName = TemplateOption["id"];
/* What a preview may show: a chosen template, or the track's own. */
export type PreviewTemplate = TemplateName | "track";

export const TRACK_TEMPLATE_LABEL = "תבנית המסלול";
export const TRACK_TEMPLATE_DESCRIPTION = "העיצוב המקורי של המערכת, לפי מסלול פיתוח או מכירות.";

export const templateLabel = (options: readonly TemplateOption[], template: TemplateName | null): string =>
  template === null ? TRACK_TEMPLATE_LABEL : (options.find((option) => option.id === template)?.label ?? template);
