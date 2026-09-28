import { ChevronDown, Search } from "lucide-react";
import { useId, useState } from "react";

import type { Requirement } from "@/api/analyses";
import type { DocumentCandidate } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { Input } from "@/ui/Input";
import { LtrText } from "@/ui/LtrText";
import { ViewSwitch } from "@/ui/ViewSwitch";
import { cx } from "@/ui/cx";
import { type FactFilter, candidateIncluded, factGroups, includableFactIds } from "../../model/factGroups";
import type { FactRanking } from "../../model/selectionManifest";
import { type FactChoice, FactRow } from "./FactRow";

interface FactSelectionListProps {
  /* The loaded plan was activated from an AI proposal, so its saved marks are the AI's. */
  aiProposed: boolean;
  busy: boolean;
  candidates: readonly DocumentCandidate[];
  changes: ReadonlyMap<string, "added" | "removed">;
  excluded: readonly string[];
  filter: FactFilter;
  onChoose: (factId: string, choice: FactChoice) => void;
  onFilterChange: (filter: FactFilter) => void;
  onIncludeAll: (factIds: readonly string[]) => void;
  pinned: readonly string[];
  rankings: ReadonlyMap<string, FactRanking>;
  savedExcluded: readonly string[];
  savedPinned: readonly string[];
  supportsByFact: ReadonlyMap<string, readonly Requirement[]>;
}

export const FactSelectionList = ({
  aiProposed,
  busy,
  candidates,
  changes,
  excluded,
  filter,
  onChoose,
  onFilterChange,
  onIncludeAll,
  pinned,
  rankings,
  savedExcluded,
  savedPinned,
  supportsByFact,
}: FactSelectionListProps) => {
  const searchId = useId();
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState<readonly string[]>([]);
  const groups = factGroups(candidates, pinned, excluded, query, filter);
  const narrowed = query.trim() !== "" || filter !== "all";
  const includedCount = candidates.filter((candidate) => candidateIncluded(candidate, pinned, excluded)).length;
  const overriddenCount = candidates.filter(
    (candidate) => pinned.includes(candidate.fact_id) || excluded.includes(candidate.fact_id),
  ).length;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="max-w-full overflow-x-auto">
          <ViewSwitch
            label="סינון העובדות"
            onChange={onFilterChange}
            options={[
              { label: `הכל (${candidates.length})`, value: "all" },
              { label: `בקורות החיים (${includedCount})`, value: "included" },
              { label: `לא נכללות (${candidates.length - includedCount})`, value: "omitted" },
              { label: `שינויים מפורשים (${overriddenCount})`, value: "overridden" },
            ]}
            value={filter}
          />
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
            className="rtl-placeholder w-56 max-w-full pr-10"
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
          <p className="text-support text-cv-text-muted">
            {filter === "overridden" && query.trim() === ""
              ? "אין קיבועים או החרגות. כל העובדות נקבעות לפי דירוג המנוע."
              : "אין עובדה שתואמת את החיפוש או את המסנן."}
          </p>
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-3">
          {groups.map((group) => {
            const open = narrowed || expanded.includes(group.section);
            const includable = includableFactIds(group, pinned, excluded);
            const panelId = `${searchId}-${group.section.replace(/\s+/g, "-")}`;
            const changed = group.items.filter((candidate) => changes.has(candidate.fact_id)).length;

            return (
              <section className="overflow-hidden rounded-surface border border-cv-border" key={group.section}>
                <div className="flex flex-wrap items-center justify-between gap-3 bg-cv-surface-muted px-4 py-2.5">
                  <button
                    aria-controls={panelId}
                    aria-expanded={open}
                    className="flex min-h-11 min-w-0 flex-1 items-center gap-3 rounded-control text-start disabled:cursor-default"
                    disabled={narrowed}
                    onClick={() =>
                      setExpanded((current) =>
                        open ? current.filter((section) => section !== group.section) : [...current, group.section],
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
                    <span className="flex min-w-0 flex-col">
                      <LtrText className="text-support font-semibold text-cv-text">{group.section}</LtrText>
                      <span className="text-caption text-cv-text-muted">
                        {group.included} מתוך {group.total} בקורות החיים
                        {changed === 0 ? null : ` · ${changed} שונו בהצעת ה־AI`}
                      </span>
                    </span>
                  </button>

                  {includable.length === 0 ? null : (
                    <Button disabled={busy} onClick={() => onIncludeAll(includable)} variant="ghost">
                      הכללת כל הסעיף
                    </Button>
                  )}
                </div>

                <ul className="flex flex-col" hidden={!open} id={panelId}>
                  {group.items.map((candidate) => (
                    <FactRow
                      aiProposed={aiProposed}
                      busy={busy}
                      candidate={candidate}
                      change={changes.get(candidate.fact_id)}
                      excluded={excluded}
                      key={candidate.fact_id}
                      onChoose={onChoose}
                      pinned={pinned}
                      ranking={rankings.get(candidate.fact_id)}
                      savedExcluded={savedExcluded}
                      savedPinned={savedPinned}
                      supports={supportsByFact.get(candidate.fact_id) ?? []}
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
