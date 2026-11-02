import { Link } from "react-router-dom";

import type { ApplicationListItem } from "@/api/contracts";
import { preparationResumeDestination } from "@/features/preparation";
import { InitialTile } from "@/ui/InitialTile";
import { Skeleton } from "@/ui/Skeleton";
import { cardClasses } from "@/ui/surface";
import { cx } from "@/ui/cx";
import { formatRelativeUpdate } from "../model/applicationListPresentation";
import { ApplicationStageBadge, PreparationMeter } from "./ApplicationListStatuses";

/* One column on a phone; from the large breakpoint as many 300px-or-wider columns as the
   row beside the action hub holds - two on a laptop, three on a wide screen. */
const cardGridClasses =
  "m-0 grid list-none gap-2.5 p-0 lg:grid-cols-[repeat(auto-fill,minmax(18.75rem,1fr))] lg:gap-3.5";

/* One Application as the design draws it: the employer's initial, the role as the
   card's title with the employer and when it last moved under it, and one line for where
   it stands - the recruitment stage's chip and the CV's step bar.

   The whole card is one link, into the Application at the step the server recommends (a
   Ready CV opens on its ready step). Everything the board used to stack on a card - a
   next-step block, a ⋮ menu, a fit chip - is the Application's own screen's now, one tap
   away; the board answers "where does each one stand" and nothing else. */
const ApplicationCard = ({ item, returned }: { item: ApplicationListItem; returned: boolean }) => (
  <li>
    <Link
      className={cardClasses(
        cx(
          "flex h-full flex-col gap-3 p-3.5 text-cv-text transition-colors hover:border-cv-border-strong lg:gap-3.5 lg:p-4.5",
          returned && "cv-returned",
        ),
      )}
      data-application-id={item.id}
      to={preparationResumeDestination(item)}
    >
      <span className="flex min-w-0 items-center gap-3">
        <InitialTile className="max-lg:size-10 max-lg:text-heading-sm" name={item.company} />
        <span className="min-w-0 flex-1">
          {/* Isolated rather than `dir="auto"` on the line: a Latin role keeps its own
              order but the line stays right-aligned with the Hebrew ones around it. */}
          <span className="block truncate text-heading-sm font-bold lg:text-heading-card">
            <bdi>{item.target_role}</bdi>
          </span>
          <span className="block truncate text-support text-cv-text-muted">
            <span dir="auto">{item.company}</span> · עודכן{" "}
            <time dateTime={item.updated_at}>{formatRelativeUpdate(item.updated_at)}</time>
          </span>
        </span>
      </span>
      <span className="flex min-w-0 items-center gap-2.5">
        <ApplicationStageBadge item={item} phoneIcon />
        <PreparationMeter item={item} />
      </span>
    </Link>
  </li>
);

export const ApplicationCardsView = ({
  items,
  returnedId,
}: {
  items: readonly ApplicationListItem[];
  /* The Application the reader just came back from: its card is ringed for a moment
     (styles.css, `cv-returned`) so the eye finds it, and nothing about its place changes. */
  returnedId: string | null;
}) => (
  <ul aria-label="כרטיסי מועמדויות" className={cardGridClasses}>
    {items.map((item) => (
      <ApplicationCard item={item} key={item.id} returned={returnedId === item.id} />
    ))}
  </ul>
);

const skeletonCards = ["skeleton-1", "skeleton-2", "skeleton-3", "skeleton-4"];

/* The first load reserves the card grid it will be replaced by, line for line: the
   initial and the two lines beside it, then the stage chip and the step bar. Drawn with
   the `Skeleton` primitive so it sweeps like every other waiting region. */
export const ApplicationCardsSkeleton = () => (
  <output aria-label="טוען את המועמדויות" className={cardGridClasses}>
    {skeletonCards.map((key) => (
      <span className={cardClasses("flex flex-col gap-3.5 p-4.5")} key={key}>
        <span className="flex items-center gap-3">
          <Skeleton className="block size-11 shrink-0" />
          <span className="flex-1 space-y-2">
            <Skeleton className="block h-4 w-3/5" />
            <Skeleton className="block h-3 w-2/5" />
          </span>
        </span>
        <span className="flex items-center gap-2.5">
          <Skeleton className="block h-6 w-24" />
          <Skeleton className="block h-1.5 flex-1" />
        </span>
      </span>
    ))}
  </output>
);
