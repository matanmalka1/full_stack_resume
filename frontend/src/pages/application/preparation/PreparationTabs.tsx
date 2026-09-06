import { type KeyboardEvent, type ReactNode, useRef } from "react";

import { cx } from "../../../ui/cx";

export type PreparationTab = "decisions" | "facts" | "analysis";

export interface PreparationTabSpec {
  /* A count of things still waiting on the reader. `null` is not "zero": the diagnostics
     tab has nothing to count, and a badge reading 0 beside it would claim it does. */
  badge: number | null;
  id: PreparationTab;
  label: string;
  /* Diagnostics is a place to read, not a place to act. It is drawn quieter for that
     reason rather than being hidden behind a link nobody finds. */
  secondary?: boolean;
}

export const tabId = (tab: PreparationTab): string => `preparation-tab-${tab}`;

export const tabPanelId = (tab: PreparationTab): string => `preparation-panel-${tab}`;

/* The three questions this screen answers, as one tablist: what the reader must decide,
   which facts the CV will carry, and what the analysis found. They used to be one scroll,
   so the decision at the top and the diagnosis explaining it at the bottom were the same
   column of same-weight cards.

   Every panel stays mounted and is hidden with `hidden` rather than unmounted: a search
   term, an opened disclosure, and a half-filled reason survive a tab switch, and no query
   is refetched by moving between them. */
export const PreparationTabs = ({
  active,
  onSelect,
  tabs,
}: {
  active: PreparationTab;
  onSelect: (tab: PreparationTab) => void;
  tabs: readonly PreparationTabSpec[];
}) => {
  const refs = useRef(new Map<PreparationTab, HTMLButtonElement>());

  /* The shell is RTL, so the arrow that moves "forward" is the one pointing at the next
     tab on screen: left. Home and End jump to the ends of the list, as APG asks. */
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

  return (
    <div
      aria-label="חלקי מסך ההכנה"
      className="flex flex-wrap gap-1 rounded-surface border border-cv-border bg-cv-surface-muted p-1"
      role="tablist"
    >
      {tabs.map((tab) => {
        const selected = tab.id === active;

        return (
          <button
            aria-controls={tabPanelId(tab.id)}
            aria-selected={selected}
            className={cx(
              "flex min-h-11 flex-1 items-center justify-center gap-2 rounded-control px-4 text-support font-semibold transition-colors duration-200",
              selected
                ? "bg-cv-surface text-cv-accent shadow-surface"
                : tab.secondary === true
                  ? "text-cv-text-muted hover:bg-cv-surface/60"
                  : "text-cv-text hover:bg-cv-surface/60",
            )}
            id={tabId(tab.id)}
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
            <span>{tab.label}</span>
            {tab.badge === null ? null : (
              <span
                className={cx(
                  "rounded-pill px-2 py-0.5 text-support font-bold",
                  tab.badge === 0
                    ? "bg-cv-surface-sunken text-cv-text-muted"
                    : selected
                      ? "bg-cv-accent text-cv-on-accent"
                      : "bg-cv-accent-soft text-cv-accent",
                )}
              >
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};

/* One panel of the tablist. Hidden rather than unmounted, and always labelled by its own
   tab, so assistive tech reads the pair as one control and its region. */
export const PreparationTabPanel = ({
  active,
  children,
  tab,
}: {
  active: boolean;
  children: ReactNode;
  tab: PreparationTab;
}) => (
  <div
    aria-labelledby={tabId(tab)}
    className="flex flex-col gap-5"
    hidden={!active}
    id={tabPanelId(tab)}
    role="tabpanel"
    tabIndex={0}
  >
    {children}
  </div>
);
