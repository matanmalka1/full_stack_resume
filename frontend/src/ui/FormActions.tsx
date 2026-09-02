import type { HTMLAttributes, ReactNode } from "react";

import { cx } from "./cx";

interface FormActionsProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  divided?: boolean;
}

export const FormActions = ({ children, className, divided = false, ...rest }: FormActionsProps) => (
  <div
    className={cx(
      "flex flex-wrap justify-end gap-3",
      divided ? "border-t border-cv-border pt-4" : undefined,
      className,
    )}
    {...rest}
  >
    {children}
  </div>
);
