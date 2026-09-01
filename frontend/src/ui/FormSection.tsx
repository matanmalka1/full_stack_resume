import type { ReactNode } from "react";

import { cx } from "./cx";

interface FormSectionProps {
  /* Sits at the end of the section header: a counter, a status, or a compact control
     that belongs to this group rather than to one field inside it. */
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
  description?: ReactNode;
  divided?: boolean;
  title: ReactNode;
}

/* A.2: a long form reads as a few named groups rather than one undifferentiated column.
   The group is a real `fieldset` so the grouping the eye sees is the grouping assistive
   technology announces. `legend` is taken out of the header's flow — a floated legend
   lays out inconsistently inside flex — and the visible title is a sibling. */
export const FormSection = ({ aside, children, className, description, divided = true, title }: FormSectionProps) => {
  return (
    <fieldset className={cx("min-w-0 border-0 p-0", className)}>
      <legend className="sr-only">{title}</legend>
      <div className={cx(divided ? "border-b border-cv-border pb-2" : undefined)}>
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <p aria-hidden="true" className="text-heading-sm font-bold tracking-tight text-cv-text">
            {title}
          </p>
          {aside === undefined ? null : <div className="text-support text-cv-text-muted">{aside}</div>}
        </div>
        {description === undefined ? null : (
          <p className="mt-1 text-support leading-6 text-cv-text-muted">{description}</p>
        )}
      </div>
      <div className="mt-4 flex flex-col gap-4">{children}</div>
    </fieldset>
  );
};
