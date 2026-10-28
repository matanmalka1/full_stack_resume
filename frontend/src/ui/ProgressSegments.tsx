import { type ClassValue, cx } from "./cx";

interface ProgressSegmentsProps {
  className?: ClassValue;
  /* How many segments are done, counted from the reading start. */
  done: number;
  /* Names the progress for assistive tech, e.g. "קורות חיים: 3 מתוך 5". Absent, the bar
     is decorative - for a card whose visible text already says the same. */
  label?: string;
  total: number;
}

/* A short run of equal segments, the done ones filled with the accent: how far a CV has
   come through its steps, read at a glance on a card. Filled and empty segments differ in
   colour and the count is always said in words beside or inside it (A.2). */
export const ProgressSegments = ({ className, done, label, total }: ProgressSegmentsProps) => (
  <div
    aria-hidden={label === undefined ? true : undefined}
    aria-label={label}
    className={cx("grid min-w-0 flex-1 gap-0.75", className)}
    role={label === undefined ? undefined : "img"}
    style={{ gridTemplateColumns: `repeat(${Math.max(total, 1)}, minmax(0, 1fr))` }}
  >
    {Array.from({ length: total }, (_, index) => (
      <span
        className={cx("h-1.25 rounded-pill", index < done ? "bg-cv-accent" : "bg-cv-border")}
        // Positional and static: the segments never reorder.
        // oxlint-disable-next-line react/no-array-index-key
        key={index}
      />
    ))}
  </div>
);
