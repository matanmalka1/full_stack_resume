import type { HTMLAttributes, ReactNode } from "react";

import { cx } from "./cx";

interface LtrTextProps extends HTMLAttributes<HTMLSpanElement> {
  children: ReactNode;
  mono?: boolean;
}

/* A.3 LTR island: URLs, IDs, ETags, error codes, filenames, English source text. */
export const LtrText = ({ children, className, mono = false, ...rest }: LtrTextProps) => {
  return (
    <span className={cx(mono ? "mono-code" : "ltr-island", className)} {...rest}>
      {children}
    </span>
  );
};
