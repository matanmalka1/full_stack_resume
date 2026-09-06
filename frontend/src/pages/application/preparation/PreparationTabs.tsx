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

  /* The tab that carries no decision splits off from the pair that does. Item ii asked
     for a quieter style on that tab, and same-row, dimmer text left it reading as one more
     option in the same choice - a reader scanning the row still had to work out which of
     three equally-shaped buttons was the one asking nothing of them. Standing apart, in
     its own outlined button beside the segmented pair rather than inside it, the shape
     itself says "not one of the two things to decide between" before the label is read.
     Both groups stay inside one `role="tablist"`, so arrow keys and the tab order still
     move through every tab as one set regardless of how they are laid out. */
  const primary = tabs.filter((tab) => tab.secondary !== true);
  const secondary = tabs.filter((tab) => tab.secondary === true);

  const renderTab = (tab: PreparationTabSpec, className: string) => {
    const selected = tab.id === active;

    return (
      <button
        aria-controls={tabPanelId(tab.id)}
        aria-selected={selected}
        className={cx(
          "flex min-h-11 items-center justify-center gap-2 rounded-control text-support font-semibold transition-colors duration-200",
          className,
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
  };

  return (
    <div aria-label="חלקי מסך ההכנה" className="flex flex-wrap items-center justify-between gap-3" role="tablist">
      <div className="flex flex-1 gap-1 rounded-surface border border-cv-border bg-cv-surface-muted p-1">
        {primary.map((tab) =>
          renderTab(
            tab,
            cx(
              "flex-1 px-4",
              tab.id === active ? "bg-cv-surface text-cv-accent shadow-surface" : "text-cv-text hover:bg-cv-surface/60",
            ),
          ),
        )}
      </div>
      {secondary.map((tab) =>
        renderTab(
          tab,
          cx(
            "border px-4",
            tab.id === active
              ? "border-cv-border-strong bg-cv-surface text-cv-text shadow-surface"
              : "border-cv-border bg-cv-surface text-cv-text-muted hover:bg-cv-surface-muted",
          ),
        ),
      )}
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
