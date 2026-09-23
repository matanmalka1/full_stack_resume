import { ChevronLeft, ChevronRight } from "lucide-react";

import { buttonClasses } from "@/ui/Button";
import { IconButton } from "@/ui/IconButton";
import { cx } from "@/ui/cx";
import { pageWindow } from "../model/applicationListPresentation";

interface ApplicationListPaginationProps {
  matchedCount: number;
  offset: number;
  pageSize: number;
  visibleCount: number;
  onOffsetChange: (offset: number) => void;
}

/* Numbered pages between two arrows. The arrows keep their words as names, so the pager
   still reads "previous / next" to a screen reader and on keyboard; the numbers let the
   reader jump rather than step. Pages are derived from the server's match count and the
   fixed page size - the offset in the URL stays the only state. */
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

  const pageCount = Math.max(1, Math.ceil(matchedCount / pageSize));
  const currentPage = Math.floor(offset / pageSize) + 1;

  return (
    <nav aria-label="ניווט בין דפי המועמדויות" className="mt-5 flex flex-wrap items-center justify-between gap-3">
      <p className="text-support text-cv-text-muted tabular-nums">{`${offset + 1}–${offset + visibleCount} מתוך ${matchedCount}`}</p>
      <div className="flex items-center gap-1">
        <IconButton
          aria-label="הקודם"
          disabled={offset === 0}
          onClick={() => onOffsetChange(Math.max(0, offset - pageSize))}
          variant="secondary"
        >
          <ChevronRight aria-hidden="true" className="size-icon-md" />
        </IconButton>
        {pageWindow(currentPage, pageCount).map((page, index) =>
          page === "gap" ? (
            <span aria-hidden="true" className="px-1 text-support text-cv-text-muted" key={`gap-${index}`}>
              …
            </span>
          ) : (
            <button
              aria-current={page === currentPage ? "page" : undefined}
              aria-label={`עמוד ${page}`}
              className={buttonClasses(
                page === currentPage ? "primary" : "secondary",
                cx("min-w-11 tabular-nums", page === currentPage && "pointer-events-none"),
                "icon",
              )}
              key={page}
              onClick={() => onOffsetChange((page - 1) * pageSize)}
              type="button"
            >
              {page}
            </button>
          ),
        )}
        <IconButton
          aria-label="הבא"
          disabled={!hasMore}
          onClick={() => onOffsetChange(offset + pageSize)}
          variant="secondary"
        >
          <ChevronLeft aria-hidden="true" className="size-icon-md" />
        </IconButton>
      </div>
    </nav>
  );
};
