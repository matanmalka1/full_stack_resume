import type { ButtonHTMLAttributes, ReactNode } from "react";

import { type ClassValue, cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";

/* Focus comes from the global :focus-visible rule in styles.css (A.2). No component
   opts in by hand, and none clears the outline. */
const baseButtonClasses =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-control px-4 text-support font-semibold transition-all duration-200 active:translate-y-px disabled:pointer-events-none disabled:translate-y-0 disabled:opacity-60";

/* Lift is reserved for the one emphasized action on a screen (A.1). A secondary or
   ghost control that rises on hover competes with it for the eye and makes a row of
   equal-weight buttons twitch under the pointer, so those two change color only. */
const variantButtonClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-cv-accent text-cv-on-accent shadow-surface hover:-translate-y-0.5 hover:bg-cv-accent-hover hover:shadow-floating",
  secondary:
    "border border-cv-border bg-cv-surface text-cv-text shadow-surface hover:border-cv-border-strong hover:bg-cv-surface-muted",
  ghost: "text-cv-accent hover:bg-cv-accent-soft",
  destructive:
    "bg-cv-blocker text-cv-on-accent shadow-surface hover:-translate-y-0.5 hover:bg-cv-blocker-hover",
};

/* Exported so a router Link can carry button styling without a polymorphic component. */
export const buttonClasses = (variant: ButtonVariant = "primary", className?: ClassValue): string =>
  cx(baseButtonClasses, variantButtonClasses[variant], className);

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  pending?: boolean;
  pendingLabel?: ReactNode;
  variant?: ButtonVariant;
}

export const Button = ({
  children,
  className,
  disabled,
  pending = false,
  pendingLabel,
  type,
  variant = "primary",
  ...rest
}: ButtonProps) => {
  return (
    <button
      aria-busy={pending || undefined}
      className={buttonClasses(variant, className)}
      disabled={disabled || pending}
      type={type ?? "button"}
      {...rest}
    >
      {pending && pendingLabel !== undefined ? pendingLabel : children}
    </button>
  );
};
