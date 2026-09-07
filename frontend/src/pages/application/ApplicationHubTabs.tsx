import { Briefcase, Layers3, Sparkles } from "lucide-react";
import { type KeyboardEvent, type ReactNode, type Ref, useRef } from "react";

import type { ApplicationDetail } from "../../api/contracts";
import { cx } from "../../ui/cx";

export type ApplicationHubTab = "job" | "preparation" | "artifacts";

type ApplicationHubBadgeTone = "neutral" | "warning" | "success" | "accent";

export interface ApplicationHubTabSpec {
  badge?: string | number | null;
  badgeTone?: ApplicationHubBadgeTone;
  icon: typeof Sparkles;
  id: ApplicationHubTab;
  label: string;
}

const BADGE_TONE_CLASSES: Record<ApplicationHubBadgeTone, string> = {
  accent: "bg-cv-accent-soft text-cv-accent",
  neutral: "bg-cv-surface-muted text-cv-text-muted",
  success: "bg-cv-success-soft text-cv-success",
  warning: "bg-cv-warning-soft text-cv-warning",
};

export const hubTabId = (tab: ApplicationHubTab): string => `app-hub-tab-${tab}`;
export const hubTabPanelId = (tab: ApplicationHubTab): string => `app-hub-panel-${tab}`;

export const buildApplicationHubTabs = (
  detail: ApplicationDetail,
  openDecisionsCount: number,
): readonly ApplicationHubTabSpec[] => {
  const isReady = detail.preparation_state === "ready";

  return [
    {
      id: "preparation",
      label: "הכנת קורות חיים",
      icon: Sparkles,
      badge: openDecisionsCount > 0 ? `${openDecisionsCount} להכרעה` : isReady ? "מוכן" : null,
      badgeTone: openDecisionsCount > 0 ? "warning" : isReady ? "success" : "neutral",
    },
    {
      id: "job",
      label: "משרה",
      icon: Briefcase,
      badge: `גרסה ${detail.latest_snapshot.version_number}`,
      badgeTone: "neutral",
    },
    {
      id: "artifacts",
      label: "תוצרים",
      icon: Layers3,
      badge: detail.latest_ready_revision_id != null ? "גרסה מאושרת" : null,
      badgeTone: "success",
    },
  ];
};

interface HubTabButtonProps {
  isActive: boolean;
  onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void;
  onSelect: (tab: ApplicationHubTab) => void;
  ref: Ref<HTMLButtonElement>;
  tab: ApplicationHubTabSpec;
}

const HubTabButton = ({ isActive, onKeyDown, onSelect, ref, tab }: HubTabButtonProps) => {
  const Icon = tab.icon;

  return (
    <button
      aria-controls={hubTabPanelId(tab.id)}
      aria-selected={isActive}
      className={cx(
        "group relative inline-flex items-center gap-2 rounded-control px-3.5 py-2 text-support font-semibold transition-all duration-150 sm:px-4",
        isActive
          ? "border border-cv-border-strong/40 bg-cv-surface text-cv-text shadow-surface"
          : "border border-transparent text-cv-text-muted hover:border-cv-border hover:bg-cv-surface/70 hover:text-cv-text",
      )}
      id={hubTabId(tab.id)}
      onClick={() => onSelect(tab.id)}
      onKeyDown={onKeyDown}
      ref={ref}
      role="tab"
      tabIndex={isActive ? 0 : -1}
      type="button"
    >
      <Icon
        aria-hidden="true"
        className={cx(
          "size-4 shrink-0 transition-colors",
          isActive ? "text-cv-accent" : "text-cv-text-muted group-hover:text-cv-text",
        )}
      />
      <span>{tab.label}</span>

      {tab.badge ? (
        <span
          className={cx(
            "rounded-control px-1.5 py-0.5 text-xs font-semibold leading-none",
            BADGE_TONE_CLASSES[tab.badgeTone ?? "neutral"],
          )}
        >
          {tab.badge}
        </span>
      ) : null}

      {isActive ? (
        <span
          aria-hidden="true"
          className="absolute -bottom-2.5 inset-x-2 h-0.5 rounded-full bg-cv-accent"
        />
      ) : null}
    </button>
  );
};

interface HubTabPanelProps {
  active: ApplicationHubTab;
  children: ReactNode;
  tab: ApplicationHubTab;
}

export const HubTabPanel = ({ active, children, tab }: HubTabPanelProps) => (
  <div
    className={active === tab ? "block space-y-6" : "hidden"}
    id={hubTabPanelId(tab)}
    role="tabpanel"
  >
    {children}
  </div>
);

interface ApplicationHubTabsProps {
  active: ApplicationHubTab;
  detail: ApplicationDetail;
  onSelect: (tab: ApplicationHubTab) => void;
  openDecisionsCount?: number;
}

export const ApplicationHubTabs = ({
  active,
  detail,
  onSelect,
  openDecisionsCount = 0,
}: ApplicationHubTabsProps) => {
  const refs = useRef(new Map<ApplicationHubTab, HTMLButtonElement>());
  const tabs = buildApplicationHubTabs(detail, openDecisionsCount);

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const index = tabs.findIndex((tab) => tab.id === active);
    const next =
      event.key === "ArrowLeft"
        ? index + 1
        : event.key === "ArrowRight"
          ? index - 1
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? tabs.length - 1
              : null;
    if (next === null) {
      return;
    }
    event.preventDefault();
    const bounded = (next + tabs.length) % tabs.length;
    const target = tabs[bounded];
    if (target !== undefined) {
      onSelect(target.id);
      refs.current.get(target.id)?.focus();
    }
  };

  return (
    <nav
      aria-label="לשוניות מועמדות"
      className="border-b border-cv-border bg-cv-surface/50 pb-2"
    >
      <div className="flex flex-wrap items-center gap-1 sm:gap-2" role="tablist">
        {tabs.map((tab) => (
          <HubTabButton
            isActive={tab.id === active}
            key={tab.id}
            onKeyDown={onKeyDown}
            onSelect={onSelect}
            ref={(element) => {
              if (element === null) {
                refs.current.delete(tab.id);
              } else {
                refs.current.set(tab.id, element);
              }
            }}
            tab={tab}
          />
        ))}
      </div>
    </nav>
  );
};
