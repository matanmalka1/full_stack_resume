import { ChevronDown, Lock, Search } from "lucide-react";
import { useId, useState } from "react";

import type { SelectionPlanCandidate } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Checkbox } from "@/ui/Checkbox";
import { EmptyState } from "@/ui/EmptyState";
import { LtrText } from "@/ui/LtrText";
import { StatusBadge } from "@/ui/StatusBadge";
import { Input } from "@/ui/Input";
import { cx } from "@/ui/cx";
import { omissionReasonLabels, selectionOutcomeLabels } from "../../model/selectionLabels";
import { candidateIncluded, candidateLocked, factGroups, factTotals, includableFactIds } from "../../model/factGroups";

const factLabel = (candidate: SelectionPlanCandidate): string => candidate.text ?? "לא ניתן לקרוא את העובדה הזו מהידע.";

/* One candidate line. The two overrides stay two controls: pinning and excluding are
   independent decisions laid over a computed outcome ("נבחרה" / "לא נכללה" / "נקבעה
   במפורש"), and collapsing them into one include/exclude toggle would throw away the
   difference between "the engine chose this" and "I chose this". */
const FactRow = ({
  busy,
  candidate,
  excluded,
  onToggleExcluded,
  onTogglePinned,
  pinned,
}: {
  busy: boolean;
  candidate: SelectionPlanCandidate;
  excluded: readonly string[];
  onToggleExcluded: (factId: string, checked: boolean) => void;
  onTogglePinned: (factId: string, checked: boolean) => void;
  pinned: readonly string[];
}) => {
  const locked = candidateLocked(candidate);
  const included = candidateIncluded(candidate, pinned, excluded);

  return (
    <li className="flex flex-col gap-2 border-t border-cv-border p-4">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <p className="min-w-0 flex-1 text-body text-cv-text" dir="auto">
          {factLabel(candidate)}
        </p>
        {locked ? (
          <StatusBadge icon={Lock} tone="neutral">
            רכיב קבוע
          </StatusBadge>
        ) : (
          <StatusBadge tone={included ? "success" : "neutral"}>{included ? "נכללת" : "לא נכללת"}</StatusBadge>
        )}
      </div>

      <p className="text-support text-cv-text-muted">
        {selectionOutcomeLabels[candidate.outcome]}
        {candidate.reason == null ? "" : ` · ${omissionReasonLabels[candidate.reason]}`}
      </p>

      {locked ? (
        <p className="text-support text-cv-text-muted">רכיב מבני שנשמר לפי כללי המסמך ואינו ניתן לקיבוע או להחרגה.</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Checkbox
            checked={pinned.includes(candidate.fact_id)}
            disabled={busy || candidate.text == null}
            onChange={(event) => onTogglePinned(candidate.fact_id, event.target.checked)}
          >
            קיבוע העובדה
          </Checkbox>
          <Checkbox
            checked={excluded.includes(candidate.fact_id)}
            disabled={busy || candidate.text == null}
            onChange={(event) => onToggleExcluded(candidate.fact_id, event.target.checked)}
          >
            החרגת העובדה
          </Checkbox>
        </div>
      )}
    </li>
  );
};

/* The plan's candidates, grouped by the CV section they belong to.

   Flat, the list was 27 same-shaped rows with the section printed at the end of each
   one's metadata line - so the only way to answer "what will the experience section say"
   was to read all of them. Grouped, each section carries its own live count, can be
   collapsed, and can be filled in one press; the search runs across every group, so a
   fact can still be found without knowing where it lives. */
export const FactSelectionList = ({
  busy,
  candidates,
  excluded,
  onIncludeAll,
  onToggleExcluded,
  onTogglePinned,
  pinned,
}: {
  busy: boolean;
  candidates: readonly SelectionPlanCandidate[];
  excluded: readonly string[];
  onIncludeAll: (factIds: readonly string[]) => void;
  onToggleExcluded: (factId: string, checked: boolean) => void;
  onTogglePinned: (factId: string, checked: boolean) => void;
  pinned: readonly string[];
}) => {
  const searchId = useId();
  const [query, setQuery] = useState("");
  /* Collapsed state is per section and starts open: a reader arriving to check what the
     CV will carry should see it, not a row of closed drawers. */
  const [collapsed, setCollapsed] = useState<readonly string[]>([]);
  const groups = factGroups(candidates, pinned, excluded, query);
  const totals = factTotals(candidates, pinned, excluded);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <div>
          <p className="text-support text-cv-text-muted">
            {totals.total} עובדות בסך הכול · {totals.included} נכללות · {totals.excluded} לא נכללות · {totals.locked}{" "}
            רכיבים קבועים
          </p>
          <p className="mt-0.5 text-support text-cv-text-muted">
            קיבוע והחרגה כאן ניתנים לשינוי גם בעורך הטיוטה - בכרטיס "ביסוס עובדתי" ובפאנל "מחזור חיי העובדות".
          </p>
        </div>

        <div className="relative">
          <label className="sr-only" htmlFor={searchId}>
            חיפוש בעובדות
          </label>
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute start-3.5 top-1/2 size-icon-md -translate-y-1/2 text-cv-text-muted"
          />
          <Input
            className="rtl-placeholder w-64 max-w-full ps-10"
            dir="auto"
            id={searchId}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="חיפוש בעובדות…"
            type="search"
            value={query}
          />
        </div>
      </div>

      {groups.length === 0 ? (
        <EmptyState>
          <p className="text-support text-cv-text-muted">אין עובדה שתואמת את החיפוש הזה.</p>
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-3">
          {groups.map((group) => {
            const open = !collapsed.includes(group.section);
            const includable = includableFactIds(group, pinned, excluded);
            const panelId = `${searchId}-${group.section.replace(/\s+/g, "-")}`;

            return (
              <section className="overflow-hidden rounded-surface border border-cv-border" key={group.section}>
                <div className="flex flex-wrap items-center justify-between gap-3 bg-cv-surface-muted px-4 py-2.5">
                  <button
                    aria-controls={panelId}
                    aria-expanded={open}
                    className="flex min-h-11 min-w-0 flex-1 items-center gap-3 rounded-control text-start"
                    onClick={() =>
                      setCollapsed((current) =>
                        open ? [...current, group.section] : current.filter((section) => section !== group.section),
                      )
                    }
                    type="button"
                  >
                    <ChevronDown
                      aria-hidden="true"
                      className={cx(
                        "size-icon-md shrink-0 text-cv-text-muted transition-transform duration-200",
                        open ? "rotate-0" : "rotate-90",
                      )}
                    />
                    <LtrText className="text-support font-semibold text-cv-text">{group.section}</LtrText>
                    <span className="rounded-pill bg-cv-surface-sunken px-2.5 py-0.5 text-support text-cv-text-muted">
                      {group.included} מתוך {group.total} נכללות
                    </span>
                  </button>

                  {includable.length === 0 ? null : (
                    <Button disabled={busy} onClick={() => onIncludeAll(includable)} variant="secondary">
                      הכללת כל הסעיף
                    </Button>
                  )}
                </div>

                <ul className="flex flex-col bg-cv-surface" hidden={!open} id={panelId}>
                  {group.items.map((candidate) => (
                    <FactRow
                      busy={busy}
                      candidate={candidate}
                      excluded={excluded}
                      key={candidate.fact_id}
                      onToggleExcluded={onToggleExcluded}
                      onTogglePinned={onTogglePinned}
                      pinned={pinned}
                    />
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
};
