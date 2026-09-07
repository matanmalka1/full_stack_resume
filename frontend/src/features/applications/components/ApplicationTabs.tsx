import { Briefcase, Layers3, Sparkles } from "lucide-react";

import type { ApplicationDetail } from "@/api/contracts";
import { Tabs, type TabSpec } from "@/ui/Tabs";

export type ApplicationTab = "job" | "preparation" | "artifacts";

export const APPLICATION_TAB_GROUP = "application";

export const isApplicationTab = (value: string | null): value is ApplicationTab =>
  value === "job" || value === "preparation" || value === "artifacts";

/* The three things an Application is: the work of preparing its CV, the posting it is
   for, and the files that work produced. Preparation leads because it is the only one of
   the three that is ever waiting on the reader; the badge says what it is waiting for.

   The row is the shared `Tabs` primitive - roving tabindex, the APG key contract, the
   panel pairing - so this file holds only which tabs exist and what each announces. */
const applicationTabs = (detail: ApplicationDetail, openDecisionsCount: number): TabSpec<ApplicationTab>[] => [
  {
    badge:
      openDecisionsCount > 0 ? `${openDecisionsCount} להכרעה` : detail.preparation_state === "ready" ? "מוכן" : null,
    badgeTone: openDecisionsCount > 0 ? "warning" : "success",
    icon: Sparkles,
    id: "preparation",
    label: "הכנת קורות חיים",
  },
  {
    badge: `גרסה ${detail.latest_snapshot.version_number}`,
    badgeTone: "neutral",
    icon: Briefcase,
    id: "job",
    label: "משרה",
  },
  {
    badge: detail.latest_ready_revision_id == null ? null : "גרסה מאושרת",
    badgeTone: "success",
    icon: Layers3,
    id: "artifacts",
    label: "תוצרים",
  },
];

export const ApplicationTabs = ({
  active,
  detail,
  onSelect,
  openDecisionsCount,
}: {
  active: ApplicationTab;
  detail: ApplicationDetail;
  onSelect: (tab: ApplicationTab) => void;
  openDecisionsCount: number;
}) => (
  <Tabs
    active={active}
    group={APPLICATION_TAB_GROUP}
    label="לשוניות מועמדות"
    onSelect={onSelect}
    tabs={applicationTabs(detail, openDecisionsCount)}
  />
);
