import type { ButtonHTMLAttributes, ReactNode } from "react";

import { type ClassValue, cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";

/* Focus comes from the global :focus-visible rule in styles.css (A.2). No component
   opts in by hand, and none clears the outline. */
const baseButtonClasses =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-control px-4 text-support font-semibold transition-all duration-200 active:translate-y-px disabled:pointer-events-none disabled:translate-y-0 disabled:opacity-60";

const variantButtonClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-cv-accent text-cv-on-accent shadow-surface hover:-translate-y-0.5 hover:bg-cv-accent-hover hover:shadow-floating",
  secondary:
    "border border-cv-border bg-cv-surface text-cv-text shadow-surface hover:-translate-y-0.5 hover:border-cv-border-strong hover:bg-cv-surface-muted",
  ghost: "text-cv-accent hover:bg-cv-accent-soft",
  destructive:
    "bg-cv-blocker text-cv-on-accent shadow-surface hover:-translate-y-0.5 hover:bg-cv-blocker-hover",
};

/* Exported so a router Link can carry button styling without a polymorphic component. */
export const buttonClasses = (variant: ButtonVariant = "primary", className?: ClassValue): string =>
  cx(baseButtonClasses, variantButtonClasses[variant], className);

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: ButtonVariant;
}

export const Button = ({ children, className, type, variant = "primary", ...rest }: ButtonProps) => {
  return (
    <button className={buttonClasses(variant, className)} type={type ?? "button"} {...rest}>
      {children}
    </button>
  );
};
