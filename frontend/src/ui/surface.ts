import { cx } from "./cx";

/* The border and radius are the shared visual contract for a surface, while the
   element remains the caller's choice. This keeps articles, forms, disclosures,
   dialogs, and document previews semantically intact instead of forcing them through
   the section-based Card component. */
export const surfaceClasses = (className?: string): string =>
  cx("rounded-surface border border-cv-hairline", className);

/* The design's card: a white surface on the grey canvas, 16px corners, a hairline edge
   and a faint shadow. `Card` draws it; a list item or a link that is a card takes the
   same classes. */
export const cardClasses = (className?: string): string =>
  surfaceClasses(cx("bg-cv-surface shadow-surface", className));
