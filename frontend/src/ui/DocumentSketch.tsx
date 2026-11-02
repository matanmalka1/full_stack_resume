import { cx } from "./cx";
import { PAGE_HEIGHT_PX, PAGE_WIDTH_PX } from "./documentPage";

/* The sketch is a fixed drawing: its bars never reorder, so their place is their key. */
/* oxlint-disable react/no-array-index-key */

/* The bars of a CV's first page, top to bottom: a name, a line under it, then three
   sections of a heading over its lines. Widths are shares of the page's width. */
const SKETCH = [
  { kind: "name", width: "w-3/5" },
  { kind: "subtitle", width: "w-2/5" },
  { kind: "gap" },
  { kind: "heading", width: "w-1/3" },
  { kind: "line", width: "w-full" },
  { kind: "line", width: "w-11/12" },
  { kind: "line", width: "w-full" },
  { kind: "gap" },
  { kind: "heading", width: "w-1/3" },
  { kind: "line", width: "w-full" },
  { kind: "line", width: "w-5/6" },
  { kind: "line", width: "w-11/12" },
  { kind: "line", width: "w-2/3" },
  { kind: "gap" },
  { kind: "heading", width: "w-1/3" },
  { kind: "line", width: "w-full" },
  { kind: "line", width: "w-4/5" },
] as const;

/* Heights in the page's own pixels; the scale shrinks them with the page. */
const barClasses = {
  name: "h-7 bg-cv-accent",
  subtitle: "h-3.5 bg-cv-border-strong",
  heading: "h-4 bg-cv-text-muted",
  line: "h-2.5 bg-cv-border",
} as const;

/* A CV page that is on its way: where its parts will sit, laid over the page's box until
   the document paints. Drawn at the page's own size and scaled exactly as the frame
   beside it is, so it has the same proportions at every zoom and in every thumbnail.
   Decorative - the screen's own text says what is loading. */
export const DocumentSketch = ({ scale }: { scale: number }) => (
  <div
    aria-hidden="true"
    className="absolute left-0 top-0 flex origin-top-left flex-col gap-4 bg-cv-surface px-18 py-20"
    style={{ height: PAGE_HEIGHT_PX, transform: `scale(${scale})`, width: PAGE_WIDTH_PX }}
  >
    {SKETCH.map((bar, index) =>
      bar.kind === "gap" ? (
        <span className="h-4" key={index} />
      ) : (
        <span className={cx("cv-skeleton rounded-sm", bar.width, barClasses[bar.kind])} key={index} />
      ),
    )}
  </div>
);
