import type { Classification } from "../api/analyses";
import type { Emphasis, Language, ProfileName, Track } from "../api/contracts";
import type { StatusTone } from "../ui/status";
import type { SummaryItem } from "../ui/SummaryList";

/* Keyed by the generated unions, so a classification value added to the backend fails
   the frontend build instead of reaching the review form untranslated. The runtime
   option lists are derived from these maps rather than written a second time. */
export const trackLabels: Record<Track, string> = {
  development: "פיתוח",
  sales: "מכירות",
  "tech-sales": "מכירות טכניות",
};

export const profileLabels: Record<ProfileName, string> = {
  development: "פיתוח",
  "field-sales": "מכירות שטח",
  "account-manager": "מנהל לקוחות",
  "key-account-manager": "מנהל לקוחות אסטרטגיים",
  "sdr-bdr": "פיתוח לידים",
  "account-executive": "סוגר עסקאות",
  "business-development": "פיתוח עסקי",
  "sales-management": "ניהול מכירות",
  "tech-sales": "מכירות טכניות",
  "pre-sales-solutions-consultant": "יועץ פתרונות טרום־מכירה",
};

export const emphasisLabels: Record<Emphasis, string> = {
  "development-balanced": "פיתוח מאוזן",
  "development-backend": "פיתוח צד שרת",
  "development-ai": "פיתוח בינה מלאכותית",
  "new-business": "לקוחות חדשים",
  "account-growth": "צמיחת לקוחות קיימים",
  leadership: "ניהול והובלה",
  "tech-consultative-sales": "מכירה טכנית מייעצת",
  "balanced-sales": "מכירות מאוזנות",
};

export const languageLabels: Record<Language, string> = {
  en: "אנגלית",
  he: "עברית",
};

/* Fit has no generated union: it lives inside the analysis document, which is carried
   as an opaque object on the wire on purpose. It is therefore declared here and checked
   by membership at the read, which is what makes an unrecognized value render as absent
   rather than as `undefined`. */
export type FitLevel = "high" | "medium" | "low";

export const fitLabels: Record<FitLevel, string> = {
  high: "התאמה גבוהה",
  medium: "התאמה בינונית",
  low: "התאמה נמוכה",
};

export const fitTones: Record<FitLevel, StatusTone> = {
  high: "success",
  medium: "neutral",
  low: "warning",
};

/* The backend's `OverrideKey` vocabulary, named for a reader. It doubles as the term
   list above, so a value the user decided is called the same thing in the summary and in
   the note saying they decided it. A key this build does not recognise is skipped at the
   read rather than printed, since an internal token teaches nothing. */
export const overrideKeyLabels: Record<string, string> = {
  track: "מסלול",
  profile: "פרופיל",
  emphasis: "דגש",
  language: "שפה",
  fit: "התאמה",
};

export const gapSeverityLabels: Record<"hard" | "warning", string> = {
  hard: "פער חוסם",
  warning: "פער לתשומת לב",
};

/* One derivation, used by every select on the review form: the option list is the map's
   own keys, so a label added above becomes an option without a second edit. */
export const optionsFrom = <T extends string>(labels: Record<T, string>): [T, string][] =>
  Object.entries(labels).map(([value, label]) => [value as T, label as string]);

const UNKNOWN = "לא ידוע";

/* The four classification terms, in one place because two screens state them: the review
   form, where each is a decision that may be overridden, and the analysis panel, where
   they are what the draft will be built from. They have to read identically in both, so
   the terms and the "unknown" fallback are defined once rather than copied. */
export const classificationItems = (classification: Classification): SummaryItem[] => [
  {
    term: overrideKeyLabels.track,
    value: classification.track === null ? UNKNOWN : trackLabels[classification.track],
  },
  {
    term: overrideKeyLabels.profile,
    value: classification.profile === null ? UNKNOWN : profileLabels[classification.profile],
  },
  {
    term: overrideKeyLabels.emphasis,
    value: classification.emphasis === null ? UNKNOWN : emphasisLabels[classification.emphasis],
  },
  {
    term: overrideKeyLabels.language,
    value: classification.language === null ? UNKNOWN : languageLabels[classification.language],
  },
];
