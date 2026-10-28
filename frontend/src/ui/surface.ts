import { cx } from "./cx";

/* The border and radius are the shared visual contract for a surface, while the
   element remains the caller's choice. This keeps articles, forms, disclosures,
   dialogs, and document previews semantically intact instead of forcing them through
   the section-based Card component. */
export const surfaceClasses = (className?: string): string => cx("rounded-surface border border-cv-border", className);

/* The default content separator: flat, square and shadowless. Rounded surfaces are
   reserved for controls and content that genuinely floats above the page. */
export const flatSurfaceClasses = (className?: string): string => cx("border border-cv-hairline", className);

/* A content card on the canvas, as the desktop design draws every panel: white, rounded,
   a faint hairline and a shadow only just there. Unlike `surfaceClasses` it does not
   float - its shadow is `card`, not `floating` - it only lifts a panel off a grey canvas.

   "wide" applies it from the large breakpoint only and leaves the element flat below it,
   for a panel whose phone design is still the flat region; "always" applies it at every
   width. */
export const raisedSurfaceClasses = (className?: string, from: "always" | "wide" = "always"): string =>
  from === "always"
    ? cx("rounded-surface border border-cv-hairline bg-cv-surface shadow-card", className)
    : cx("border border-cv-hairline lg:rounded-surface lg:bg-cv-surface lg:shadow-card", className);
