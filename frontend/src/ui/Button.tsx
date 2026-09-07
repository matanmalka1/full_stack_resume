import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { type ClassValue, cx } from "./cx";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";

/* Focus comes from the global :focus-visible rule in styles.css (A.2). No component
   opts in by hand, and none clears the outline. */
const baseButtonClasses =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-control px-4 text-support font-semibold transition-all duration-200 active:translate-y-px disabled:pointer-events-none disabled:translate-y-0 disabled:shadow-none disabled:cursor-not-allowed";

/* Lift is reserved for the one emphasized action on a screen (A.1). A secondary or
   ghost control that rises on hover competes with it for the eye and makes a row of
   equal-weight buttons twitch under the pointer, so those two change color only.

   Disabled is a flat neutral fill, the same idiom every text control on this design
   system already disables with (`Input`, `Select`: `disabled:bg-cv-surface-muted
   disabled:text-cv-text-muted`) - not the accent colour dimmed by opacity. Dimming
   `cv-accent` with opacity keeps its hue: at 60% over a white surface the saturated blue
   composites to a pale blue-violet that a reader can still mistake for the same button,
   pressable. Flattening to the surface-muted/text-muted pair reads as "not this one"
   regardless of which variant it disables. */
const variantButtonClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-cv-accent text-cv-on-accent shadow-surface hover:-translate-y-0.5 hover:bg-cv-accent-hover hover:shadow-floating disabled:bg-cv-surface-muted disabled:text-cv-text-muted",
  secondary:
    "border border-cv-border bg-cv-surface text-cv-text shadow-surface hover:border-cv-border-strong hover:bg-cv-surface-muted disabled:border-cv-border disabled:bg-cv-surface-muted disabled:text-cv-text-muted",
  ghost: "text-cv-accent hover:bg-cv-accent-soft disabled:text-cv-text-muted",
  destructive:
    "bg-cv-blocker text-cv-on-accent shadow-surface hover:-translate-y-0.5 hover:bg-cv-blocker-hover disabled:bg-cv-surface-muted disabled:text-cv-text-muted",
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
      <span className="inline-grid items-center justify-items-center">
        <span
          aria-hidden={pending || undefined}
          className={cx("col-start-1 row-start-1 inline-flex items-center gap-2", pending && "invisible")}
        >
          {children}
        </span>
        {pending ? (
          <span className="col-start-1 row-start-1 inline-flex items-center gap-2">
            <LoaderCircle aria-hidden="true" className="size-4 shrink-0 animate-spin" />
            {pendingLabel ?? children}
          </span>
        ) : null}
      </span>
    </button>
  );
};
