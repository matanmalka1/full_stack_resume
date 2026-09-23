import type { ApplicationListItem, ApplicationSort } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import type { ViewMode } from "../model/applicationViews";
import { ApplicationCardsView } from "./ApplicationCardsView";
import { ApplicationListPagination } from "./ApplicationListPagination";
import { ApplicationListTable } from "./ApplicationListTable";
import { ApplicationPipelineView } from "./ApplicationPipelineView";

interface ApplicationListResultsProps {
  clearingApplicationId: string | null;
  fetching: boolean;
  items: readonly ApplicationListItem[];
  matchedCount: number;
  offset: number;
  pageSize: number;
  sort: ApplicationSort;
  viewMode: ViewMode;
  onClearFilters: () => void;
  onClearNextAction: (item: ApplicationListItem) => void;
  onOffsetChange: (offset: number) => void;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestDelete: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
  onSortChange: (sort: ApplicationSort) => void;
}

/* The result region: one page of Applications in whichever view is chosen, the message
   that replaces it when the filters match none, and the pager.
   
   It exists so the page above it composes four named regions rather than carrying a
   three-way view switch, two empty states, and a fetching wrapper inline. Which view is
   drawn is a presentation decision and stays here; what is in the page and how it was
   narrowed remain the page's. */
export const ApplicationListResults = ({
  clearingApplicationId,
  fetching,
  items,
  matchedCount,
  offset,
  pageSize,
  sort,
  viewMode,
  onClearFilters,
  onClearNextAction,
  onOffsetChange,
  onRequestClose,
  onRequestDelete,
  onRequestUpdate,
  onSortChange,
}: ApplicationListResultsProps) => {
  if (items.length === 0) {
    return (
      <EmptyState className="bg-cv-surface">
        <p className="text-body text-cv-text">אין מועמדות שמתאימה לסינון.</p>
        <div className="mt-5 flex justify-center">
          <Button onClick={onClearFilters} variant="secondary">
            ניקוי הסינון
          </Button>
        </div>
      </EmptyState>
    );
  }

  return (
    /* A refetch dims the page it is replacing instead of unmounting it, so a filter
       change does not drop the reader back to a blank region. `QueryState` still owns
       the first load and every failure. */
    <div aria-busy={fetching ? true : undefined} className={fetching ? "opacity-60 transition-opacity" : undefined}>
      {viewMode === "cards" ? (
        <ApplicationCardsView
          clearingApplicationId={clearingApplicationId}
          items={items}
          onClearNextAction={onClearNextAction}
          onRequestClose={onRequestClose}
          onRequestDelete={onRequestDelete}
          onRequestUpdate={onRequestUpdate}
        />
      ) : viewMode === "pipeline" ? (
        <ApplicationPipelineView items={items} onRequestUpdate={onRequestUpdate} />
      ) : (
        <ApplicationListTable
          clearingApplicationId={clearingApplicationId}
          items={items}
          onClearNextAction={onClearNextAction}
          onSortChange={onSortChange}
          sort={sort}
          onRequestClose={onRequestClose}
          onRequestDelete={onRequestDelete}
          onRequestUpdate={onRequestUpdate}
        />
      )}
      <ApplicationListPagination
        matchedCount={matchedCount}
        offset={offset}
        onOffsetChange={onOffsetChange}
        pageSize={pageSize}
        visibleCount={items.length}
      />
    </div>
  );
};
