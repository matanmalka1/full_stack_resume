import { cx } from "./cx";

/* The border and radius are the shared visual contract for a surface, while the
   element remains the caller's choice. This keeps articles, forms, disclosures,
   dialogs, and document previews semantically intact instead of forcing them through
   the section-based Card component. */
export const surfaceClasses = (className?: string): string =>
  cx("rounded-surface border border-cv-border", className);
