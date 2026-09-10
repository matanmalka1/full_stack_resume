import { type ClassValue, cx } from "./cx";

/* A region that has been asked for and is on its way, drawn at the size it will be.

   It is the third answer to waiting, beside the two the Operations feature owns. Those
   report durable work: a run exists, it has a status, it can be cancelled or retried. This
   reports nothing of the kind - a document is being read, and the only thing worth saying
   is where it will appear. Dressing that as an Operation card would claim a run the server
   never queued; leaving it as a line of muted text made the one screen in the flow that
   does not look like the rest of the flow.

   The zero-width space is what gives a skeleton with no height of its own the height of
   one line of whatever type it sits in - which is how a placeholder standing in for a line
   of text reserves exactly the box that text will take, at every breakpoint, without a
   copy of the type scale here to go stale.

   No display or size in the base: `cx` is a plain concat with no conflict resolution, so a
   default here could not be overridden predictably. Every caller states both, because the
   point is to match the content rather than to be a generic grey box.

   Always `aria-hidden` - the region's own live text says that it is loading, and the shape
   tells a screen reader nothing. */
export const Skeleton = ({ className }: { className?: ClassValue }) => (
  <span aria-hidden="true" className={cx("cv-skeleton rounded-surface bg-cv-surface-muted", className)}>
    {"​"}
  </span>
);
