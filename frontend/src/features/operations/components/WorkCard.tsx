import { useId, type ReactNode } from "react";

import { Card } from "@/ui/Card";
import { LiveRegion } from "@/ui/LiveRegion";
import { StatusBadge } from "@/ui/StatusBadge";

/* The one shape work in flight is reported in.

   A screen learns that work is happening in stages - the command was accepted, the
   Operation record arrived, the run reached a phase, it finished - and each stage used to
   pick its own presentation: a bare line of muted text before the record existed, a
   bordered card once it did. The reader saw the same fact ("this is working") in two
   geometries a second apart, and the second one displaced the page under it.

   So the frame is fixed here and the stages fill it in. What changes between them is the
   badge and the sentence; the container, its padding, and the position of the heading do
   not move. */
export const WorkCardFrame = ({
  badge,
  children,
  heading,
}: {
  badge: ReactNode;
  children?: ReactNode;
  heading: ReactNode;
}) => {
  /* Per instance rather than one constant for the frame. Two of these can be on a screen
     for a moment where one step's finished run is still on record and the next step's work
     has been sent - the editor between an approval and the render Operation it queues -
     and a shared literal made that moment two elements answering to one id. */
  const headingId = useId();

  return (
    <Card aria-labelledby={headingId} className="p-5">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <h2 className="text-body font-semibold text-cv-text" id={headingId}>
          {heading}
        </h2>
        <div className="flex flex-wrap items-center gap-3">{badge}</div>
      </div>

      <div className="mt-4 flex flex-col gap-4">{children}</div>
    </Card>
  );
};

/* Work this client has asked for, before any Operation record is on screen to report it.

   It stands in two windows the reader cannot tell apart from a running Operation and
   should not have to: between an accepted `202` and the watch that follows the record it
   named, and between a screen's arrival and the first read that carries the projection's
   live work. Both used to be a line of muted text that the Operation's card then replaced.

   It states only what this client actually knows - the work was asked for - and claims no
   status the backend has not reported. The moment a record exists, `ActiveOperationPanel`
   takes the same frame over and fills in the real one. */
export const PendingWorkCard = ({ heading, note }: { heading: ReactNode; note: ReactNode }) => (
  <WorkCardFrame badge={<StatusBadge tone="progress">נשלחה לביצוע</StatusBadge>} heading={heading}>
    <p className="text-support leading-6 text-cv-text-muted" dir="auto">
      {note}
    </p>
    <LiveRegion>{note}</LiveRegion>
  </WorkCardFrame>
);
