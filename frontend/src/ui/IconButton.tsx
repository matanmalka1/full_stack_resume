import type { ComponentProps, ReactNode } from "react";

import { buttonClasses, type ButtonVariant } from "./Button";

const iconSizes = { default: "icon", md: "icon-md", sm: "icon-sm" } as const;

interface IconButtonProps extends Omit<ComponentProps<"button">, "aria-label" | "children"> {
  "aria-label": string;
  children: ReactNode;
  /* "default" is the 44px touch target. The smaller two are for a control repeated on
     every row or card, where a full-size target per record would crowd the content it
     serves; each such record still keeps a full-size route to the same place. */
  size?: keyof typeof iconSizes;
  variant?: ButtonVariant;
}

export const IconButton = ({
  "aria-label": label,
  children,
  className,
  size = "default",
  type = "button",
  variant = "ghost",
  ...rest
}: IconButtonProps) => (
  <button aria-label={label} className={buttonClasses(variant, className, iconSizes[size])} type={type} {...rest}>
    {children}
  </button>
);
