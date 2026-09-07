import type { LucideIcon } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useRef } from "react";

import { cx } from "./cx";

export type TabBadgeTone = "neutral" | "warning" | "success" | "accent";

export interface TabSpec<TId extends string> {
  /* A count or a short word beside the label. `null` is not "zero": a tab with nothing
     to count carries no badge, and a badge reading 0 beside it would claim it does. */
  badge?: ReactNode;
  badgeTone?: TabBadgeTone;
  icon?: LucideIcon;
  id: TId;
  label: string;
}

const badgeToneClasses: Record<TabBadgeTone, string> = {
  accent: "bg-cv-accent-soft text-cv-accent",
  neutral: "bg-cv-surface-sunken text-cv-text-muted",
  success: "bg-cv-success-soft text-cv-success",
  warning: "bg-cv-warning-soft text-cv-warning",
};

const tabId = (group: string, tab: string): string => `${group}-tab-${tab}`;

const tabPanelId = (group: string, tab: string): string => `${group}-panel-${tab}`;

interface TabsProps<TId extends string> {
  active: TId;
  /* Namespaces generated ids when more than one tablist appears on a screen. */
  group: string;
  label: string;
  onSelect: (tab: TId) => void;
  tabs: readonly TabSpec<TId>[];
  className?: string;
  /* "underline" is the screen's own top-level row; "segmented" is a pill of equal-width
     segments for a region inside it. Two skins over one behaviour, not a configuration
     surface: everything else about the control is identical. */
  variant?: "underline" | "segmented";
}

/* Shared roving-tabindex and APG arrow/Home/End behavior. The shell is RTL, so ArrowLeft
   advances to the next visually positioned tab. */
export const Tabs = <TId extends string>({
  active,
  group,
  label,
  onSelect,
  tabs,
  className,
  variant = "underline",
}: TabsProps<TId>) => {
  const refs = useRef(new Map<TId, HTMLButtonElement>());

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
    const target = tabs[(next + tabs.length) % tabs.length];
    if (target === undefined) {
      return;
    }
    onSelect(target.id);
    refs.current.get(target.id)?.focus();
  };

  const segmented = variant === "segmented";

  return (
    <div
      aria-label={label}
      className={cx(
        segmented
          ? "flex gap-1 rounded-surface bg-cv-surface-muted p-1"
          : "flex flex-wrap items-center gap-1 border-b border-cv-border pb-2 sm:gap-2",
        className,
      )}
      role="tablist"
    >
      {tabs.map((tab) => {
        const selected = tab.id === active;
        const Icon = tab.icon;

        return (
          <button
            aria-controls={tabPanelId(group, tab.id)}
            aria-selected={selected}
            className={cx(
              "group relative inline-flex min-h-11 items-center gap-2 rounded-control text-support font-semibold transition-colors duration-150",
              segmented
                ? "flex-1 justify-center border"
                : "px-3.5 py-2 sm:px-4 " +
                    (selected ? "border border-cv-border-strong/40" : "border border-transparent"),
              selected
                ? segmented
                  ? "border-cv-accent bg-cv-surface text-cv-text shadow-surface"
                  : "bg-cv-surface text-cv-text shadow-surface"
                : segmented
                  ? "border-transparent text-cv-text-muted hover:bg-cv-surface/60"
                  : "text-cv-text-muted hover:border-cv-border hover:bg-cv-surface/70 hover:text-cv-text",
            )}
            id={tabId(group, tab.id)}
            key={tab.id}
            onClick={() => onSelect(tab.id)}
            onKeyDown={onKeyDown}
            ref={(node) => {
              if (node === null) {
                refs.current.delete(tab.id);
              } else {
                refs.current.set(tab.id, node);
              }
            }}
            role="tab"
            tabIndex={selected ? 0 : -1}
            type="button"
          >
            {Icon === undefined ? null : (
              <Icon
                aria-hidden="true"
                className={cx(
                  "size-4 shrink-0 transition-colors",
                  selected ? "text-cv-accent" : "text-cv-text-muted group-hover:text-cv-text",
                )}
              />
            )}
            <span>{tab.label}</span>
            {tab.badge == null ? null : (
              <span
                className={cx(
                  "rounded-pill px-2 py-0.5 text-xs font-bold leading-none",
                  badgeToneClasses[tab.badgeTone ?? "neutral"],
                )}
              >
                {tab.badge}
              </span>
            )}
            {selected && !segmented ? (
              <span aria-hidden="true" className="absolute -bottom-2.5 inset-x-2 h-0.5 rounded-full bg-cv-accent" />
            ) : null}
          </button>
        );
      })}
    </div>
  );
};

/* One panel of a tablist. Hidden rather than unmounted, and always labelled by its own
   tab, so assistive tech reads the pair as one control and its region - and so a search
   term, an opened disclosure and a half-filled form survive a tab switch without any
   query being refetched. */
export const TabPanel = ({
  active,
  children,
  group,
  tab,
}: {
  active: boolean;
  children: ReactNode;
  group: string;
  tab: string;
}) => (
  <div
    aria-labelledby={tabId(group, tab)}
    className="flex flex-col gap-5"
    hidden={!active}
    id={tabPanelId(group, tab)}
    role="tabpanel"
    tabIndex={0}
  >
    {children}
  </div>
);
