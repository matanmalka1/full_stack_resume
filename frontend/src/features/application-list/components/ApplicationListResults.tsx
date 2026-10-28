import { Filter } from "lucide-react";

import type { ApplicationListItem } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { cx } from "@/ui/cx";
import type { ViewMode } from "../model/applicationViews";
import { ApplicationCardsView } from "./ApplicationCardsView";
import { ApplicationListPagination } from "./ApplicationListPagination";
import { ApplicationPipelineView } from "./ApplicationPipelineView";

interface ApplicationListResultsProps {
  /* The page on screen is the previous query's, held while a changed query is read. */
  replacing: boolean;
  items: readonly ApplicationListItem[];
  matchedCount: number;
  offset: number;
  pageSize: number;
  recruitmentStatusCounts: Readonly<Record<string, number>>;
  recruitmentStatusFilter: readonly string[] | undefined;
  /* The Application the reader just came back from, marked for a moment. */
  returnedId: string | null;
  viewMode: ViewMode;
  onClearFilters: () => void;
  onOffsetChange: (offset: number) => void;
  onRequestClose: (item: ApplicationListItem) => void;
  onRequestDelete: (item: ApplicationListItem) => void;
  onRequestDetails: (item: ApplicationListItem) => void;
  onRequestUpdate: (item: ApplicationListItem) => void;
}

/* The result region: one page of Applications in whichever view is chosen, the message
   that replaces it when the filters match none, and the pager.
   
   It exists so the page above it composes four named regions rather than carrying the
   view switch, two empty states, and a fetching wrapper inline. Which view is
   drawn is a presentation decision and stays here; what is in the page and how it was
   narrowed remain the page's. */
export const ApplicationListResults = ({
  replacing,
  items,
  matchedCount,
  offset,
  pageSize,
  recruitmentStatusCounts,
  recruitmentStatusFilter,
  returnedId,
  viewMode,
  onClearFilters,
  onOffsetChange,
  onRequestClose,
  onRequestDelete,
  onRequestDetails,
  onRequestUpdate,
}: ApplicationListResultsProps) => {
  if (items.length === 0) {
    return (
      /* On a phone the message stands on the canvas under a filter mark, unframed, with
         the way out a full-size button: it is the whole region, not a gap in a list. */
      <EmptyState className="bg-cv-surface max-lg:border-0 max-lg:bg-transparent max-lg:py-12">
        <span
          aria-hidden="true"
          className="mx-auto mb-4 flex size-16 items-center justify-center rounded-surface border border-cv-border bg-cv-surface text-cv-text lg:hidden"
        >
          <Filter className="size-7" />
        </span>
        <p className="text-body text-cv-text max-lg:text-heading-sm max-lg:font-extrabold">
          אין מועמדות שמתאימה לסינון.
        </p>
        <div className="mt-5 flex justify-center">
          <Button className="max-lg:min-h-11 max-lg:px-5" onClick={onClearFilters} variant="secondary">
            ניקוי הסינון
          </Button>
        </div>
      </EmptyState>
    );
  }

  return (
    /* A changed query dims the page it is replacing instead of unmounting it, so a filter
       change does not drop the reader back to a blank region. A re-read of the same page
       does not dim it: the board polls every 1.5s while an Operation runs and re-reads on
       focus and after every action, and dimming on each of those made it flash for
       nothing. `QueryState` still owns the first load and every failure. */
    <div
      aria-busy={replacing ? true : undefined}
      className={cx("transition-opacity", replacing ? "opacity-60" : undefined)}
    >
      {viewMode === "pipeline" ? (
        <ApplicationPipelineView
          items={items}
          onRequestClose={onRequestClose}
          onRequestDelete={onRequestDelete}
          onRequestDetails={onRequestDetails}
          onRequestUpdate={onRequestUpdate}
          recruitmentStatusCounts={recruitmentStatusCounts}
          recruitmentStatusFilter={recruitmentStatusFilter}
          returnedId={returnedId}
        />
      ) : (
        <ApplicationCardsView
          items={items}
          onRequestClose={onRequestClose}
          onRequestDelete={onRequestDelete}
          onRequestDetails={onRequestDetails}
          onRequestUpdate={onRequestUpdate}
          returnedId={returnedId}
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
