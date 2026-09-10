import type { ButtonHTMLAttributes, ReactNode } from "react";

import { buttonClasses, type ButtonVariant } from "./Button";

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
  <button aria-label={label} className={buttonClasses(variant, className, "icon")} type={type} {...rest}>
    {children}
  </button>
);
