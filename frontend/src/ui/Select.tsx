import type { SelectHTMLAttributes } from "react";
import { ChevronDown } from "lucide-react";

import { cx } from "./cx";
import { controlClasses } from "./TextInput";

export const Select = ({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) => {
  return (
    <span className="relative block w-full">
      <select className={cx(controlClasses, "min-h-11 appearance-none pe-10", className)} {...rest} />
      <ChevronDown
        aria-hidden="true"
        className="pointer-events-none absolute end-3.5 top-1/2 size-4 -translate-y-1/2 text-cv-text-muted"
      />
    </span>
  );
};
