import { Search } from "lucide-react";
import type { ComponentProps } from "react";

import { cx } from "./cx";

/* ComponentProps rather than the attribute types alone: these carry `ref`, which is
   how React Hook Form binds an uncontrolled field to the primitive. */

export const Input = ({ className, type, ...rest }: ComponentProps<"input">) => {
  return (
    <input
      className={cx("cv-field cv-field-input block w-full rounded-control border px-3 py-2", className)}
      type={type ?? "text"}
      {...rest}
    />
  );
};

export const Textarea = ({ className, ...rest }: ComponentProps<"textarea">) => {
  return (
    <textarea
      className={cx(
        "cv-field cv-field-textarea block min-h-32 w-full resize-y rounded-control border px-3.5 py-2.5",
        className,
      )}
      {...rest}
    />
  );
};

/* A filter's free-text box: the input with a search mark at its inline start. The mark is
   decoration - the field's label names it - and the text starts clear of it. */
export const SearchInput = ({ className, ...rest }: Omit<ComponentProps<"input">, "type">) => (
  <div className="relative">
    <Search
      aria-hidden="true"
      className="pointer-events-none absolute inset-y-0 start-3 my-auto size-icon-md text-cv-text-muted"
    />
    <Input className={cx("!ps-9", className)} type="search" {...rest} />
  </div>
);
