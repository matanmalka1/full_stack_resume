import type { ApplicationListItem } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import type { ViewMode } from "../model/applicationViews";
import { ApplicationCardsView } from "./ApplicationCardsView";
import { ApplicationListPagination } from "./ApplicationListPagination";
import { ApplicationListTable } from "./ApplicationListTable";
import { ApplicationPipelineView } from "./ApplicationPipelineView";

interface ApplicationListResultsProps {
  fetching: boolean;
  items: readonly ApplicationListItem[];
  matchedCount: number;
  offset: number;
  pageSize: number;
  viewMode: ViewMode;
  onClearFilters: () => void;
  onOffsetChange: (offset: number) => void;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

/* The result region: one page of Applications in whichever view is chosen, the message
   that replaces it when the filters match none, and the pager.
   
   It exists so the page above it composes four named regions rather than carrying a
   three-way view switch, two empty states, and a fetching wrapper inline. Which view is
   drawn is a presentation decision and stays here; what is in the page and how it was
   narrowed remain the page's. */
export const ApplicationListResults = ({
  fetching,
  items,
  matchedCount,
  offset,
  pageSize,
  viewMode,
  onClearFilters,
  onOffsetChange,
  onRequestClose,
  onRequestUpdate,
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
        <ApplicationCardsView items={items} onRequestClose={onRequestClose} onRequestUpdate={onRequestUpdate} />
      ) : viewMode === "pipeline" ? (
        <ApplicationPipelineView items={items} onRequestUpdate={onRequestUpdate} />
      ) : (
        <ApplicationListTable items={items} onRequestClose={onRequestClose} onRequestUpdate={onRequestUpdate} />
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
