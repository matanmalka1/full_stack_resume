import type { SelectHTMLAttributes } from "react";

import { cx } from "./cx";
import { controlClasses } from "./TextInput";

export const Select = ({ className, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) => {
  return <select className={cx(controlClasses, "min-h-11", className)} {...rest} />;
};
