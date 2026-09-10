import { cx } from "./cx";

/* The border and radius are the shared visual contract for a surface, while the
   element remains the caller's choice. This keeps articles, forms, disclosures,
   dialogs, and document previews semantically intact instead of forcing them through
   the section-based Card component. */
export const surfaceClasses = (className?: string): string => cx("rounded-surface border border-cv-border", className);

/* The default content separator: flat, square and shadowless. Rounded surfaces are
   reserved for controls and content that genuinely floats above the page. */
export const flatSurfaceClasses = (className?: string): string => cx("border border-cv-hairline", className);
