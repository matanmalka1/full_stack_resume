import { BadgeCheck, Clock3, ShieldCheck, type LucideIcon } from "lucide-react";

import type { CreateFactRequest, Fact, FactStatus } from "../../api/contracts";
import type { StatusTone } from "../../ui/status";

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

export const factStatusTones: Record<FactStatus, StatusTone> = {
  pending: "warning",
  confirmed: "progress",
  canonical: "success",
};

export const factStatusIcons: Record<FactStatus, LucideIcon> = {
  pending: Clock3,
  confirmed: BadgeCheck,
  canonical: ShieldCheck,
};

export const factLabel = (fact: Fact): string => fact.renderings.he ?? fact.renderings.en ?? fact.meaning;

export const factStatusLabel = (status: string): string => factStatusLabels[status as FactStatus] ?? status;
