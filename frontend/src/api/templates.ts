import type { Settings } from "./contracts";

/* The render templates a CV can choose (backend `cv_engine/domain/templates.py`). The
   catalog arrives with the settings read; nothing here duplicates it. */
export type TemplateOption = Settings["available_templates"][number];
export type TemplateName = TemplateOption["id"];
/* What a preview may show: a chosen template, or the track's own. */
export type PreviewTemplate = TemplateName | "track";
export type SampleLanguage = "en" | "he";

export const TRACK_TEMPLATE_LABEL = "תבנית המסלול";
export const TRACK_TEMPLATE_DESCRIPTION = "העיצוב המקורי של המערכת, לפי מסלול פיתוח או מכירות.";

/* A fictional CV in one template, framed like the document preview: the browser loads
   it in a sandboxed iframe, so it never passes through `apiRequest`. It reads no user's
   data, which is what lets Settings show a template before any CV exists. */
export const templateSampleSrc = (template: PreviewTemplate, language: SampleLanguage): string =>
  `/api/v1/templates/${encodeURIComponent(template)}/sample?language=${language}`;

export const templateLabel = (options: readonly TemplateOption[], template: TemplateName | null): string =>
  template === null ? TRACK_TEMPLATE_LABEL : (options.find((option) => option.id === template)?.label ?? template);
