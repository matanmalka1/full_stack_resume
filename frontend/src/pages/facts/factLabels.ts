import { BadgeCheck, Clock3, ShieldCheck, type LucideIcon } from "lucide-react";

import type { Fact, FactStatus } from "../../api/contracts";
import type { StatusTone } from "../../ui/status";

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
