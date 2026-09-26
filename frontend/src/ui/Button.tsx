import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { type ClassValue, cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";

/* Focus comes from the global :focus-visible rule in styles.css (A.2). No component
   opts in by hand, and none clears the outline. */
const baseButtonClasses =
  "inline-flex items-center justify-center gap-2 rounded-control text-support font-semibold transition-all duration-200 active:translate-y-px disabled:pointer-events-none disabled:translate-y-0 disabled:shadow-none disabled:cursor-not-allowed";

const sizeButtonClasses = {
  compact: "min-h-8 px-2.5",
  default: "min-h-11 px-4",
  icon: "size-11 px-0",
  flush: "min-h-11 px-0",
} as const;

const variantButtonClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-cv-accent text-cv-on-accent shadow-surface hover:-translate-y-0.5 hover:bg-cv-accent-hover hover:shadow-floating disabled:bg-cv-surface-muted disabled:text-cv-text-muted",
  secondary:
    "border border-cv-border bg-cv-surface text-cv-text shadow-surface hover:border-cv-border-strong hover:bg-cv-surface-muted disabled:border-cv-border disabled:bg-cv-surface-muted disabled:text-cv-text-muted disabled:opacity-60",
  ghost: "text-cv-accent hover:bg-cv-accent-soft disabled:text-cv-text-muted",
  destructive:
    "bg-cv-blocker text-cv-on-accent shadow-surface hover:-translate-y-0.5 hover:bg-cv-blocker-hover disabled:bg-cv-surface-muted disabled:text-cv-text-muted",
};

/* Exported so a router Link can carry button styling without a polymorphic component. */
export const buttonClasses = (
  variant: ButtonVariant = "primary",
  className?: ClassValue,
  size: keyof typeof sizeButtonClasses = "default",
): string => cx(baseButtonClasses, sizeButtonClasses[size], variantButtonClasses[variant], className);

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  pending?: boolean;
  pendingLabel?: ReactNode;
  size?: keyof typeof sizeButtonClasses;
  variant?: ButtonVariant;
}

export const Button = ({
  children,
  className,
  disabled,
  pending = false,
  pendingLabel,
  size = "compact",
  type,
  variant = "primary",
  ...rest
}: ButtonProps) => {
  return (
    <button
      aria-busy={pending || undefined}
      className={buttonClasses(variant, className, size)}
      disabled={disabled || pending}
      type={type ?? "button"}
      {...rest}
    >
      <span className="inline-grid items-center justify-items-center">
        <span
          aria-hidden={pending || undefined}
          className={cx("col-start-1 row-start-1 inline-flex items-center gap-2", pending && "invisible")}
        >
          {children}
        </span>
        {pending ? (
          <span className="col-start-1 row-start-1 inline-flex items-center gap-2">
            <LoaderCircle aria-hidden="true" className="size-icon-md shrink-0 animate-spin" />
            {pendingLabel ?? children}
          </span>
        ) : null}
      </span>
    </button>
  );
};
