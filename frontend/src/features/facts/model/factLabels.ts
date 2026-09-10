import { BadgeCheck, Clock3, ShieldCheck, type LucideIcon } from "lucide-react";

import type { CreateFactRequest, Fact, FactStatus } from "@/api/contracts";
import type { Tone } from "@/ui/tone";

export type FactSource = CreateFactRequest["source"];
export type FactStyle = CreateFactRequest["resume_style"];

export const factSourceLabels: Record<FactSource, string> = {
  "common.md": "עובדות משותפות",
  "sales.md": "ניסיון במכירות",
  "development.md": "ניסיון בפיתוח",
  "situational_skills.md": "כישורים מצביים",
};

export const factStyleLabels: Record<FactStyle, string> = {
  bullet: "שורת ניסיון",
  item: "פריט",
  paragraph: "פסקה",
  heading: "כותרת",
  date: "תאריך",
  contact: "פרט קשר",
};

export const factStatusLabels: Record<FactStatus, string> = {
  pending: "ממתינה לאישור",
  confirmed: "אושרה",
  canonical: "מקור אמת",
};

export const factStatusTones: Record<FactStatus, Tone> = {
  pending: "warning",
  confirmed: "progress",
  canonical: "success",
};

export const factStatusIcons: Record<FactStatus, LucideIcon> = {
  pending: Clock3,
  confirmed: BadgeCheck,
  canonical: ShieldCheck,
};

/* The status/source unions are open strings on the wire, so a value the backend adds
   before the frontend knows it renders as itself rather than as `undefined`. The keyed
   records above stay exhaustive for the values the contract does declare. */
export const factStatusLabel = (status: string): string => factStatusLabels[status as FactStatus] ?? status;

export const factSourceLabel = (source: string): string => factSourceLabels[source as FactSource] ?? source;

export const factStyleLabel = (style: string): string => factStyleLabels[style as FactStyle] ?? style;

/* What a person calls this fact, for display only - the persisted renderings are never
   rewritten to match it. The reading language wins where the caller knows one (the draft
   editor reads a claim in the draft's own language); otherwise Hebrew leads, since this
   interface is Hebrew. `meaning` is the last resort: a fact always carries one. */
export const factLabel = (fact: Fact): string => fact.renderings.he ?? fact.renderings.en ?? fact.meaning;

export const factLabelInLanguage = (fact: Fact, language: string): string =>
  fact.renderings[language] ?? fact.renderings.en ?? fact.meaning;

/* Sources that belong to no single career track. A fact filed under one of these is
   meant to be reused across tracks, so attaching it anywhere raises nothing. */
const TRACK_NEUTRAL_SOURCES = new Set<string>(["common.md", "situational_skills.md"]);

/* Whether attaching this fact would pull it across career tracks - a development fact
   onto a sales Profile, or the reverse. Not forbidden: a fact can legitimately cross,
   and the store allows it. It is worth naming before the write because nothing else on
   the screen would tell the reader the fact came from the other track. */
export const isCrossTrackFact = (source: string, expectedSource: string | null): boolean =>
  expectedSource !== null && !TRACK_NEUTRAL_SOURCES.has(source) && source !== expectedSource;
