import type { ButtonHTMLAttributes, ReactNode } from "react";

import { buttonClasses, type ButtonVariant } from "./Button";
import { cx } from "./cx";

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "aria-label" | "children"> {
  "aria-label": string;
  children: ReactNode;
  variant?: ButtonVariant;
}

/** A square button for icon-only actions. Its accessible name is intentionally required. */
export const IconButton = ({
  "aria-label": label,
  children,
  className,
  type = "button",
  variant = "ghost",
  ...rest
}: IconButtonProps) => (
  <button aria-label={label} className={cx(buttonClasses(variant), "size-11 px-0!", className)} type={type} {...rest}>
    {children}
  </button>
);
