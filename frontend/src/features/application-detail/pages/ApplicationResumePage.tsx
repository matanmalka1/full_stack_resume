import { useQuery } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";

import { ApiProblem } from "@/api/client";
import { Button } from "@/ui/Button";
import { applicationDetailQueryOptions } from "@/api/applications";
import { useRequiredParam } from "@/navigation/useRequiredParam";
import { preparationResumeDestinationFromDetail } from "@/features/preparation";
import { LiveRegion } from "@/ui/LiveRegion";
import { PageShell } from "@/ui/PageShell";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";

/* The read before the redirect: the sentence, leading the shape of the step the reader is
   about to land on, so the swap to that step reads as the page filling in rather than as
   one screen replacing another. On a phone that is the spine's segments, the step's
   opening banner and two cards under it; on a wide screen the stepper's row, then the
   main column's card beside the aside's two - the Application screen's own layout. */
const resumeLoading = (
  <div className="flex flex-col gap-4 lg:gap-5">
    <LiveRegion className="text-body text-cv-text-muted max-lg:text-support" visuallyHidden={false}>
      בודק מהו השלב הפעיל…
    </LiveRegion>
    <div aria-hidden="true" className="flex flex-col gap-5 max-lg:hidden">
      <div className="flex items-center gap-3 rounded-surface border border-cv-border bg-cv-surface px-5 py-4">
        {[0, 1, 2].map((segment) => (
          <span className="contents" key={segment}>
            <Skeleton className="block size-6 shrink-0 rounded-pill" />
            <span className="h-0.5 flex-1 rounded-pill bg-cv-border" />
          </span>
        ))}
        <Skeleton className="block size-6 shrink-0 rounded-pill" />
      </div>
      <div className="grid grid-cols-[minmax(0,1fr)_20rem] items-start gap-5">
        <div className="flex h-64 flex-col items-start gap-3 rounded-surface border border-cv-border bg-cv-surface p-6">
          <Skeleton className="block h-4 w-2/5" />
          <Skeleton className="block h-2.5 w-full" />
          <Skeleton className="block h-2.5 w-11/12" />
          <Skeleton className="block h-2.5 w-4/5" />
          <Skeleton className="block h-2.5 w-3/5" />
        </div>
        <div className="flex flex-col gap-4">
          <Skeleton className="block h-28 w-full rounded-surface" />
          <div className="h-36 rounded-surface border border-cv-border bg-cv-surface" />
        </div>
      </div>
    </div>
    <div aria-hidden="true" className="flex flex-col gap-3 lg:hidden">
      <div className="grid grid-cols-4 gap-1.5">
        {[0, 1, 2, 3].map((segment) => (
          <span className="h-1 rounded-pill bg-cv-border" key={segment} />
        ))}
      </div>
      <Skeleton className="block h-24 w-full" />
      {[0, 1].map((card) => (
        <div
          className="flex flex-col items-start gap-2.5 rounded-surface border border-cv-border bg-cv-surface p-4"
          key={card}
        >
          <Skeleton className="block h-3.5 w-3/5" />
          <Skeleton className="block h-2.5 w-full" />
          <Skeleton className="block h-2.5 w-4/5" />
        </div>
      ))}
    </div>
  </div>
);

/* Resolve a duplicate match through the current Application projection before entering
   the wizard. Duplicate evidence has no workflow fields of its own, and must not acquire
   them merely so one link can guess where current work lives. */
export const ApplicationResumePage = () => {
  const applicationId = useRequiredParam("applicationId");
  const query = useQuery(applicationDetailQueryOptions(applicationId));

  if (query.data !== undefined && !query.isFetching && query.error === null) {
    return <Navigate replace to={preparationResumeDestinationFromDetail(applicationId, query.data)} />;
  }

  return (
    /* This resolver belongs to the workflow geometry but does not claim a workflow stage:
       it only reads the projection and redirects to the screen that owns that stage. */
    <PageShell title="ממשיך מהמקום שבו עצרת">
      <QueryState
        error={query.error}
        errorTitle="לא ניתן לטעון את פרטי המועמדות"
        loading={query.isPending || (query.data !== undefined && query.isFetching)}
        loadingState={resumeLoading}
      />
      {query.error === null || (query.error instanceof ApiProblem && query.error.problem.status === 404) ? null : (
        <Button
          onClick={() => {
            if (!query.isFetching) void query.refetch({ cancelRefetch: false });
          }}
          pending={query.isFetching}
          pendingLabel="בודק שוב…"
          variant="secondary"
        >
          ניסיון חוזר
        </Button>
      )}
    </PageShell>
  );
};
