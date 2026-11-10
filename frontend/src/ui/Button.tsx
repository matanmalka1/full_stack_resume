import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { type ClassValue, cx } from "./cx";

/* "quiet" is the muted control that sits among content - a row's tools, a record's menu, a
   dismiss mark - where an accent-coloured ghost would read as the step to take. */
export type ButtonVariant = "primary" | "secondary" | "ghost" | "quiet" | "destructive";

/* Focus comes from the global :focus-visible rule in styles.css (A.2). No component
   opts in by hand, and none clears the outline.

   Sizes follow the design: "default" is the 46px command a form or dialog ends on,
   "large" the 52px one a sheet or an empty state leads with, "compact" the 40px one that
   sits inside a card or a row. On a phone every size steps down to the iPhone's own
   scale - 34, 40 and 44px capsules, 36px round icon buttons. */
const baseButtonClasses =
  "inline-flex items-center justify-center gap-2 font-bold transition-colors duration-200 active:translate-y-px disabled:pointer-events-none disabled:translate-y-0 disabled:shadow-none disabled:cursor-not-allowed";

const sizeButtonClasses = {
  compact: "min-h-10 rounded-control-sm px-3.5 text-label max-lg:min-h-8.5 max-lg:rounded-pill max-lg:px-3.5",
  default: "min-h-11.5 rounded-control px-5 text-body max-lg:min-h-10 max-lg:rounded-pill max-lg:px-4",
  large: "min-h-13 rounded-control-lg px-5.5 text-body max-lg:min-h-11 max-lg:rounded-pill max-lg:px-5",
  icon: "size-11 rounded-control px-0 max-lg:size-9 max-lg:rounded-pill",
  "icon-md": "size-10 rounded-control-sm px-0 max-lg:size-8 max-lg:rounded-pill",
  "icon-sm": "size-8 rounded-item px-0 max-lg:size-7 max-lg:rounded-pill",
  flush: "min-h-11 rounded-control px-0 text-label max-lg:min-h-9",
} as const;

const variantButtonClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-cv-accent text-cv-on-accent hover:bg-cv-accent-hover disabled:bg-cv-surface-muted disabled:text-cv-text-muted",
  secondary:
    "border border-cv-border-strong bg-cv-surface text-cv-text hover:bg-cv-surface-muted disabled:border-cv-border disabled:bg-cv-surface-muted disabled:text-cv-text-muted disabled:opacity-60",
  ghost: "text-cv-accent hover:bg-cv-accent-soft disabled:text-cv-text-muted",
  quiet: "text-cv-text-muted hover:bg-cv-surface-muted hover:text-cv-text disabled:opacity-50",
  destructive:
    "bg-cv-blocker text-cv-on-accent hover:bg-cv-blocker-hover disabled:bg-cv-surface-muted disabled:text-cv-text-muted",
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
