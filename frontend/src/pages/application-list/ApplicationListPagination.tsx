import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "../../ui/Button";

interface ApplicationListPaginationProps {
  matchedCount: number;
  offset: number;
  pageSize: number;
  visibleCount: number;
  onOffsetChange: (offset: number) => void;
}

export const ApplicationListPagination = ({
  matchedCount,
  offset,
  pageSize,
  visibleCount,
  onOffsetChange,
}: ApplicationListPaginationProps) => {
  const hasMore = offset + visibleCount < matchedCount;

  if (offset === 0 && !hasMore) {
    return null;
  }

  return (
    <nav
      aria-label="ניווט בין דפי המועמדויות"
      className="mt-4 flex flex-wrap items-center justify-between gap-3"
    >
      <p className="text-support text-cv-text-muted">
        {`${offset + 1}–${offset + visibleCount} מתוך ${matchedCount}`}
      </p>
      <div className="flex items-center gap-2">
        <Button
          disabled={offset === 0}
          onClick={() => onOffsetChange(Math.max(0, offset - pageSize))}
          variant="secondary"
        >
          <ChevronRight aria-hidden="true" className="size-4" />
          הקודם
        </Button>
        <Button
          disabled={!hasMore}
          onClick={() => onOffsetChange(offset + pageSize)}
          variant="secondary"
        >
          הבא
          <ChevronLeft aria-hidden="true" className="size-4" />
        </Button>
      </div>
    </nav>
  );
};
