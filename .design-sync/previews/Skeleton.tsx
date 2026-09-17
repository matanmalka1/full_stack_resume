import { Skeleton } from "cv-application-frontend";

export const TextPlaceholders = () => (
  <div className="flex flex-col gap-3 p-4 max-w-sm">
    <Skeleton className="block h-7 w-48" />
    <Skeleton className="block h-4 w-full" />
    <Skeleton className="block h-4 w-5/6" />
    <Skeleton className="block h-4 w-3/4" />
  </div>
);

export const CardPlaceholder = () => (
  <div className="flex flex-col gap-4 p-4 max-w-sm">
    <div className="rounded-surface border border-cv-border p-4">
      <div className="flex items-start gap-3">
        <Skeleton className="block size-10 rounded-control shrink-0" />
        <div className="flex-1 space-y-2">
          <Skeleton className="block h-5 w-36" />
          <Skeleton className="block h-4 w-24" />
        </div>
      </div>
      <div className="mt-3 space-y-2">
        <Skeleton className="block h-4 w-full" />
        <Skeleton className="block h-4 w-5/6" />
      </div>
    </div>
    <div className="rounded-surface border border-cv-border p-4">
      <div className="flex items-start gap-3">
        <Skeleton className="block size-10 rounded-control shrink-0" />
        <div className="flex-1 space-y-2">
          <Skeleton className="block h-5 w-44" />
          <Skeleton className="block h-4 w-20" />
        </div>
      </div>
    </div>
  </div>
);
