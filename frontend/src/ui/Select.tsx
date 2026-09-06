import type { SelectHTMLAttributes } from "react";

import { cx } from "./cx";

export const Select = ({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) => {
  return (
    <select
      className={cx(
        "cv-field cv-field-select block w-full appearance-auto rounded-control border px-3 py-2.25",
        className,
      )}
      {...rest}
    />
  );
};
