import { HelpCircle, SignalHigh, SignalLow, SignalMedium } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { Classification, RequirementCoverage } from "@/api/analyses";
import { type FitLevel, isFitLevel } from "@/api/classificationValues";
import type { Emphasis, Language, ProfileName, Track } from "@/api/contracts";
import type { Tone } from "@/ui/tone";
import type { SummaryItem } from "@/ui/SummaryList";

/* Keyed by the generated unions, so a classification value added to the backend fails
   the frontend build instead of reaching the review form untranslated. The runtime
   option lists are derived from these maps rather than written a second time. */
export const trackLabels: Record<Track, string> = {
  development: "פיתוח",
  sales: "מכירות",
  "tech-sales": "מכירות טכנולוגיות",
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
  "tech-sales": "מכירות טכנולוגיות",
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

/* Fit is declared where the analysis document is read - `@/api/classificationValues` -
   because the document travels as an opaque object and the narrowing belongs to that
   boundary. What is here is what each level is called and how loudly it is drawn. */
export const fitLabels: Record<FitLevel, string> = {
  high: "התאמה גבוהה",
  medium: "התאמה בינונית",
  low: "התאמה נמוכה",
  unknown: "ההתאמה לא נבדקה",
};

/* The verdict alone is a word with no scale behind it: "high" reads as praise rather
   than as one of three values. Each level says what it means for the workflow, which is
   the part that decides whether the reader should press on or look again. */
export const fitDescriptions: Record<FitLevel, string> = {
  high: "המשרה תואמת את פרופיל המועמד. אין חסם התאמה ליצירת טיוטה.",
  medium: "התאמה חלקית. אפשר להמשיך, אך כדאי לעבור על הפערים לפני יצירת טיוטה.",
  low: "ההתאמה נמוכה לפי העובדות המאושרות. אפשר להמשיך ליצירת טיוטה, וכדאי לעבור קודם על הפערים.",
  unknown: "לא ניתן היה לחשב התאמה מדרישות המשרה. אפשר להמשיך ליצירת טיוטה ולבחון את האבחון הזמין.",
};

export const fitTones: Record<FitLevel, Tone> = {
  high: "success",
  medium: "neutral",
  low: "warning",
  unknown: "warning",
};

/* Fit is a scale, so its mark is a scale too. The tone's own icons say "warning" and
   "information", which is what a severity carries - a reader comparing rows is ranking
   them, and a rising signal reads as the rank the word already states. */
export const fitIcons: Record<FitLevel, LucideIcon> = {
  high: SignalHigh,
  medium: SignalMedium,
  low: SignalLow,
  unknown: HelpCircle,
};

/* The Application projections carry `fit_level` and `track` as open strings rather than
   as the analysis unions, so the board and the Application screen read them through
   these. The maps above stay the one place each value is named; a value this build does
   not recognise is shown as itself rather than guessed at. */
export const fitLevelLabel = (fit: string): string => (isFitLevel(fit) ? fitLabels[fit] : fit);

export const fitLevelTone = (fit: string): Tone => (isFitLevel(fit) ? fitTones[fit] : "neutral");

export const fitLevelIcon = (fit: string): LucideIcon | undefined => (isFitLevel(fit) ? fitIcons[fit] : undefined);

export const trackLabel = (track: string): string => (track in trackLabels ? trackLabels[track as Track] : track);

/* The backend's `OverrideKey` vocabulary, named for a reader. It doubles as the term
   list above, so a value the user decided is called the same thing in the summary and in
   the note saying they decided it. A key this build does not recognise is skipped at the
   read rather than printed, since an internal token teaches nothing. */
export const overrideKeyLabels: Record<string, string> = {
  track: "מסלול",
  profile: "פרופיל",
  emphasis: "דגש",
  language: "שפה",
};

/* Where the engine narrowed a reading, in words. An open string map rather than a Record
   over a union: issues travel inside the analysis document, which is an opaque object on the
   wire. A code this build does not recognise is shown raw rather than hidden - an unfamiliar
   token still tells the reader that something was narrowed. */
const analysisIssueLabels: Record<string, string> = {
  quote_not_found: "נוסח של דרישה לא אותר במודעה השמורה; הדרישה נשמרה ללא עיגון.",
  quote_ambiguous: "נוסח של דרישה מופיע במודעה יותר מפעם אחת.",
  unknown_fact: "עובדה שצוטטה אינה קיימת במאגר והוסרה מהדרישה.",
  fact_not_canonical: "עובדה שצוטטה אינה מאושרת והוסרה מהדרישה.",
  coverage_without_evidence: "כיסוי חיובי שלא נשארה לו ראיה הורד ל״לא הוכרע״.",
  duplicate_requirement: "דרישה שהופיעה פעמיים אוחדה לאחת.",
  requirement_unusable: "דרישה ריקה או לא קריאה דולגה.",
};

export const analysisIssueLabel = (code: string): string => analysisIssueLabels[code] ?? code;

/* Confidence is a 0..1 float in the document and a percentage to a reader.

   The sign is the Hebrew-side one and the whole value is written into the sentence rather
   than wrapped in an A.3 LTR island. An island is for a Latin run that must not be
   reordered - an id, a code, a filename. A percentage is a number in a Hebrew sentence,
   and isolating it pushed the run to the end of the line, so "58%" arrived on screen
   reading "%58". */
export const confidenceText = (confidence: number): string => `${Math.round(confidence * 100)}%`;

export const gapSeverityLabels: Record<"hard" | "warning", string> = {
  // Named for what it is, not for what it used to do: a hard gap is a demanded
  // requirement the facts do not support, and it blocks nothing.
  hard: "פער בדרישת חובה",
  warning: "פער לתשומת לב",
};

/* The coverage a Requirement carries independently of its gap projection: `matched` and
   `partial` have no gap at all, so this is the only place either is named for the
   reader. Ordered as a scale, like Fit's tones above - `matched` reads as the safe end
   and `unsupported` as the blocked one, with `partial` between them. `unknown` is
   not a point on that scale - it means the engine could not decide, not that the facts
   fall short, so it is never worded or toned like `unsupported`. */
export const coverageLabels: Record<RequirementCoverage, string> = {
  matched: "מכוסה",
  partial: "מכוסה חלקית",
  unsupported: "לא מכוסה",
  unknown: "לא הוכרע",
};

export const coverageTones: Record<RequirementCoverage, Tone> = {
  matched: "success",
  partial: "warning",
  unsupported: "blocker",
  unknown: "neutral",
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
