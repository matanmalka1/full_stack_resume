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
