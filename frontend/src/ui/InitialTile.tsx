import { type ClassValue, cx } from "./cx";

const sizeClasses = {
  md: "size-10 rounded-control-sm text-heading-sm",
  lg: "size-11 rounded-control text-heading-card",
} as const;

/* The first letter of a record's name on a soft square - an employer on a board card or
   an Application's details. Decorative: the name itself is always written beside it. */
export const initialOf = (name: string): string => name.trim().charAt(0).toLocaleUpperCase("he") || "?";

export const InitialTile = ({
  className,
  name,
  size = "lg",
}: {
  className?: ClassValue;
  name: string;
  size?: keyof typeof sizeClasses;
}) => (
  <span
    aria-hidden="true"
    className={cx(
      "flex shrink-0 items-center justify-center bg-cv-surface-muted font-extrabold text-cv-text",
      sizeClasses[size],
      className,
    )}
  >
    {initialOf(name)}
  </span>
);
