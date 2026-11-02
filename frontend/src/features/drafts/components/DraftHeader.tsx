import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { ApplicationDetail } from "@/api/contracts";
import { routePaths } from "@/navigation/routePaths";
import { Skeleton } from "@/ui/Skeleton";

interface DraftHeaderProps {
  /* The commands the design gives the heading's row: the preview toggle at every width,
     and on a wide screen the approval beside it. */
  actions?: ReactNode;
  applicationId: string;
  detail: ApplicationDetail | undefined;
}

/* The editor's top, as the design draws it at both widths: the way back to the
   Application, the document as the title with who it is for under it, and the commands at
   the row's far end.

   It is the route's heading itself, not a compact header above a hidden one: the title
   is the same words at every width, so one `h1` serves the reader, the route focus and
   assistive tech. On a phone the row is the screen's top bar - the back mark a bare 44px
   target at the gutter's edge, the title a step smaller - and on a wide screen the back
   mark is an outlined square beside a page-sized title. */
export const DraftHeader = ({ actions, applicationId, detail }: DraftHeaderProps) => (
  <header className="flex flex-wrap items-center gap-3.5 max-lg:-mx-2 max-lg:-mt-1.5 max-lg:flex-nowrap max-lg:gap-1">
    <Link
      aria-label="חזרה לפרטי המועמדות"
      className="flex size-10 shrink-0 items-center justify-center rounded-control-sm border border-cv-border bg-cv-surface text-cv-text transition-colors hover:bg-cv-surface-muted max-lg:size-11 max-lg:rounded-control max-lg:border-0 max-lg:bg-transparent"
      to={routePaths.application(applicationId)}
    >
      <ChevronRight aria-hidden="true" className="size-icon-lg" />
    </Link>
    <div className="min-w-0 flex-1 lg:min-w-56">
      <h1
        className="text-title font-extrabold tracking-tight text-cv-text max-lg:text-heading-sm max-lg:leading-6"
        data-route-heading
        id="route-heading"
        tabIndex={-1}
      >
        טיוטת קורות החיים
      </h1>
      {detail === undefined ? (
        <Skeleton className="mt-1 inline-block w-48 max-w-full align-middle" />
      ) : (
        <p className="mt-0.5 truncate text-label text-cv-text-muted max-lg:mt-0 max-lg:text-caption" dir="auto">
          {`${detail.application.target_role} · ${detail.application.company}`}
        </p>
      )}
    </div>
    {actions === undefined ? null : <div className="flex shrink-0 items-center gap-2.5">{actions}</div>}
  </header>
);
