import { BookOpen, Filter, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import type { ApplicationListItem, ApplicationListResponse } from "@/api/contracts";
import { returnedApplicationId } from "@/navigation/boardReturn";
import { routePaths } from "@/navigation/routePaths";
import { ApplicationDetailsSheet } from "@/features/application-detail";
import { preparationResumeDestination } from "@/features/preparation";
import { Button, buttonClasses } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { PageShell } from "@/ui/PageShell";
import { QueryState } from "@/ui/QueryState";
import { cx } from "@/ui/cx";
import { ApplicationAttentionSummary } from "../components/ApplicationAttentionSummary";
import { ApplicationCardsSkeleton, ApplicationCardsView } from "../components/ApplicationCardsView";
import { ApplicationPipelineView } from "../components/ApplicationPipelineView";
import { ApplicationPresetTabs } from "../components/ApplicationPresetTabs";
import { BoardSort, BoardViewSwitch } from "../components/BoardControls";
import { useApplicationListQuery } from "../hooks/useApplicationListQuery";
import { nextStepText } from "../model/applicationListPresentation";
import { initialViewMode, rememberViewMode, type ViewMode } from "../model/applicationViews";

/* How long the card the reader came back from stays marked. Matches `cv-returned`. */
const RETURN_HIGHLIGHT_MS = 2_400;

/* A phone's top bar has no room for the new-job command, so below the large breakpoint
   it floats over the board, above the bottom navigation, where a thumb reaches it. On a
   wide screen it is the sidebar's. */
const NewApplicationFab = () => (
  <>
    {/* Room under the last card, so the floating button never covers it. */}
    <div aria-hidden="true" className="h-16 lg:hidden" />
    <Link
      aria-label="קליטת משרה חדשה"
      className={buttonClasses(
        "primary",
        "fixed end-4 bottom-[calc(var(--cv-bottom-nav-height)+1rem)] z-(--cv-z-sticky) h-14 rounded-fab ps-4.5 pe-5 shadow-fab lg:hidden",
      )}
      to={routePaths.newApplication}
    >
      <Plus aria-hidden="true" className="size-icon-lg" />
      משרה חדשה
    </Link>
  </>
);

/* The empty board's picture: a page of a CV with a second sheet behind it and a plus on
   its corner, drawn from the product's own surfaces rather than an image. Decorative. */
const EmptyBoardMark = () => (
  <div aria-hidden="true" className="relative mx-auto mb-6 h-24 w-22">
    <span className="absolute inset-y-1.5 start-0 end-4 rotate-6 rounded-item border border-cv-border bg-cv-surface" />
    <span className="absolute inset-y-0 start-3 end-1.5 flex flex-col items-start gap-1.5 rounded-item border border-cv-border bg-cv-surface px-3 pt-4 shadow-surface">
      <span className="h-1.25 w-8 rounded-pill bg-cv-accent" />
      <span className="h-1 w-11 rounded-pill bg-cv-border" />
      <span className="h-1 w-10 rounded-pill bg-cv-border" />
      <span className="h-1 w-11 rounded-pill bg-cv-border" />
    </span>
    <span className="absolute -bottom-2 end-0 flex size-11 items-center justify-center rounded-pill bg-cv-accent text-cv-on-accent shadow-action">
      <Plus className="size-icon-lg" />
    </span>
  </div>
);

/* No Application exists yet: there is no board to act on, so the offer to start one is
   the whole page - and, since a CV is built from the reader's facts, the way to fill
   those in first. On a phone it stands unframed on the canvas with a full-width command;
   on a wide screen it fills the board's frame with the two side by side. */
const EmptyBoard = () => (
  <EmptyState className="flex flex-col items-center justify-center max-lg:border-0 max-lg:px-3 max-lg:py-14 lg:min-h-[48rem]">
    <EmptyBoardMark />
    <h2 className="text-heading-md font-extrabold text-cv-text lg:text-title">עוד אין מועמדויות</h2>
    <p className="mt-2 max-w-md text-body text-cv-text-muted">
      מדביקים מודעת משרה, והמערכת בונה ממנה קורות חיים מותאמים מתוך העובדות שלך.
    </p>
    <div className="mt-6 flex w-full flex-col items-center gap-3 lg:w-auto lg:flex-row lg:gap-2.5">
      <Link
        className={buttonClasses("primary", "w-full shadow-action lg:w-auto", "large")}
        to={routePaths.newApplication}
      >
        <Plus aria-hidden="true" className="size-icon-md lg:hidden" />
        קליטת משרה ראשונה
      </Link>
      <Link
        className={cx(
          buttonClasses("secondary", "lg:min-h-13 lg:rounded-control-lg"),
          "max-lg:min-h-11 max-lg:border-0 max-lg:bg-transparent max-lg:text-label max-lg:underline max-lg:underline-offset-4",
        )}
        to={routePaths.facts}
      >
        <BookOpen aria-hidden="true" className="size-icon-md lg:hidden" />
        קודם למלא את מאגר העובדות
      </Link>
    </div>
  </EmptyState>
);

/* The chosen slice holds nothing - a gap in the board, not an empty product - so the way
   out is to show everything again. */
const NoResults = ({ onShowAll, title }: { onShowAll?: () => void; title: string }) => (
  <EmptyState className="flex flex-col items-center justify-center max-lg:border-0 max-lg:py-24 lg:min-h-[37.5rem]">
    <span
      aria-hidden="true"
      className="mb-4 flex size-16 items-center justify-center rounded-surface border border-cv-border bg-cv-surface text-cv-text lg:size-18"
    >
      <Filter className="size-7" />
    </span>
    <p className="text-heading-sm font-extrabold text-cv-text lg:text-heading-sheet">{title}</p>
    {onShowAll === undefined ? null : (
      <Button className="mt-5" onClick={onShowAll} variant="secondary">
        הצגת כל המועמדויות
      </Button>
    )}
  </EmptyState>
);

/* "12 מועמדויות פעילות" - the open board's size, whichever slice is on screen. */
const activeCountText = (page: ApplicationListResponse): string => {
  const count = page.preset_counts.all ?? page.matched;
  return count === 1 ? "מועמדות פעילה אחת" : `${count} מועמדויות פעילות`;
};

/* The board reads top to bottom as the design draws it: the title with how many processes
   are live, the named slices, what is waiting on the reader, and the work itself - in
   cards, or in columns by recruitment stage. A card is a way into its Application; the
   stages view's cards open a details sheet first.

   The board narrows only by its slices. Finding one Application by name is the quick
   search's (⌘K, or the search button on a phone), and the commands that change a record -
   its status, closing, deleting - are its own screen's. */
export const ApplicationListPage = () => {
  const [viewMode, setViewModeState] = useState<ViewMode>(initialViewMode);
  const setViewMode = (next: ViewMode) => {
    rememberViewMode(next);
    setViewModeState(next);
  };
  const cards = viewMode === "cards";
  const { listQuery, query, updateQuery } = useApplicationListQuery({ withPreset: cards });
  const [detailsApplicationId, setDetailsApplicationId] = useState<string | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  /* Read once, from the link that left a flow screen. The history entry is then cleared
     of it, so a reload or a step back to this board does not mark the card again. */
  const [returnedId, setReturnedId] = useState(() => returnedApplicationId(location.state));
  useEffect(() => {
    if (returnedApplicationId(location.state) === null) return;
    void navigate({ pathname: location.pathname, search: location.search }, { replace: true, state: null });
  }, [location, navigate]);

  const page = listQuery.data;
  const items: readonly ApplicationListItem[] = page?.items ?? [];
  const loaded = page !== undefined;
  const empty = page?.total === 0;
  const preset = cards ? (query.preset ?? "all") : "all";

  /* Once the board holds the card, bring it into view if it is not, and let its mark go
     after a moment. The board's order is untouched: the reader finds the card where it
     is, rather than the card being moved to where the reader is. */
  useEffect(() => {
    if (returnedId === null || !loaded) return;
    const card = [...window.document.querySelectorAll<HTMLElement>("[data-application-id]")].find(
      (element) => element.dataset.applicationId === returnedId,
    );
    if (card !== undefined) {
      const box = card.getBoundingClientRect();
      if (box.top < 0 || box.bottom > window.innerHeight) {
        const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
        card.scrollIntoView?.({ behavior: still ? "auto" : "smooth", block: "center" });
      }
    }
    const timeout = window.setTimeout(() => setReturnedId(null), RETURN_HIGHLIGHT_MS);
    return () => window.clearTimeout(timeout);
  }, [loaded, returnedId]);

  const detailsApplication = items.find((item) => item.id === detailsApplicationId) ?? null;
  const detailsDestination = detailsApplication === null ? null : preparationResumeDestination(detailsApplication);
  const detailsContinue =
    detailsApplication === null || detailsDestination === null
      ? null
      : {
          label:
            detailsDestination === routePaths.ready(detailsApplication.id)
              ? "פתיחת קורות החיים המוכנים"
              : "המשך בהכנה",
          to: detailsDestination,
        };
  const showAll = () => updateQuery({ ...query, preset: undefined });
  const sort = query.sort ?? "updated";
  const setSort = (next: typeof sort) => updateQuery({ ...query, sort: next });

  /* The wide screen's controls sit on the title's row: the view switch, and in the cards
     view the order; on a phone they move into the body - see below. The cards view's
     slices are the masthead's next line, at every width: they are the first choice the
     reader makes, and the masthead's own row gap is the design's distance from the
     title. */
  const actions =
    page === undefined || empty ? undefined : (
      <>
        <div className="flex items-center gap-2.5 max-lg:hidden">
          <BoardViewSwitch onChange={setViewMode} value={viewMode} variant="compact" />
          {cards ? <BoardSort onChange={setSort} value={sort} variant="boxed" /> : null}
        </div>
        {cards ? (
          <div className="min-w-0 basis-full lg:mt-2.5">
            <ApplicationPresetTabs
              counts={page.preset_counts}
              onSelect={(next) => updateQuery({ ...query, preset: next === "all" ? undefined : next })}
              value={preset}
            />
          </div>
        ) : null}
      </>
    );

  const description =
    page === undefined || empty ? undefined : cards ? activeCountText(page) : "מועמדויות לפי שלב גיוס";

  const results = () => {
    if (page === undefined) return null;

    if (!cards) {
      return (
        <>
          <div className="lg:hidden">
            <BoardViewSwitch onChange={setViewMode} value={viewMode} variant="stretch" />
          </div>
          <ApplicationPipelineView
            items={items}
            onRequestDetails={(item) => setDetailsApplicationId(item.id)}
            recruitmentStatusCounts={page.recruitment_status_counts}
            returnedId={returnedId}
          />
        </>
      );
    }

    /* Every Application is closed: the board is empty, but the product is not. */
    if (items.length === 0 && preset === "all") {
      return <NoResults title="אין מועמדויות פעילות. מועמדויות סגורות נמצאות בחיפוש המהיר." />;
    }
    if (items.length === 0) {
      return <NoResults onShowAll={showAll} title="אין מועמדות שמתאימה לסינון." />;
    }

    /* On a phone the action hub comes before the cards; on a wide screen it is a column
       at the row's far end, beside them. */
    return (
      <>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:gap-6">
          <div className="lg:order-last">
            <ApplicationAttentionSummary />
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-2.5">
            <div className="flex items-center justify-between gap-3 lg:hidden">
              <div className="flex items-center gap-2.5">
                <h2 className="text-heading-card font-extrabold text-cv-text">מועמדויות</h2>
                <BoardViewSwitch onChange={setViewMode} value={viewMode} variant="compact" />
              </div>
              <BoardSort onChange={setSort} value={sort} variant="plain" />
            </div>
            <ApplicationCardsView items={items} returnedId={returnedId} />
          </div>
        </div>
        <NewApplicationFab />
      </>
    );
  };

  return (
    <PageShell actions={actions} description={description} measure="wide" title="לוח המועמדויות">
      <QueryState
        empty={empty}
        emptyState={<EmptyBoard />}
        error={listQuery.error}
        errorTitle="לא ניתן לטעון את המועמדויות"
        loading={listQuery.isPending}
        onRetry={() => void listQuery.refetch()}
        /* No `loadingLabel`: `loadingState` always wins over it, so a label here would be
           a string that never renders. The skeleton announces the wait itself. */
        loadingState={<ApplicationCardsSkeleton />}
      >
        {/* A changed slice dims the board it is replacing instead of unmounting it, so a
            chip press does not drop the reader back to a blank region. A re-read of the
            same board does not dim it: the board re-reads on focus and after every action,
            and dimming on each of those made it flash for nothing. */}
        <div
          aria-busy={listQuery.isPlaceholderData ? true : undefined}
          className={cx(
            "flex flex-col gap-4 transition-opacity lg:gap-5.5",
            listQuery.isPlaceholderData && "opacity-60",
          )}
        >
          {results()}
        </div>
      </QueryState>
      <ApplicationDetailsSheet
        application={
          detailsApplication === null ? null : { ...detailsApplication, closed: detailsApplication.is_closed }
        }
        continueTo={detailsContinue}
        nextStep={detailsApplication === null ? undefined : nextStepText(detailsApplication)}
        onClose={() => setDetailsApplicationId(null)}
      />
    </PageShell>
  );
};
