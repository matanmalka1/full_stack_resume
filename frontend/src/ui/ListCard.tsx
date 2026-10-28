import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { ChevronLeft } from "lucide-react";
import { Link } from "react-router-dom";

import { type ClassValue, cx } from "./cx";
import { cardClasses } from "./surface";

/* A card whose content is a list of rows divided by hairlines - a settings group, a
   phone's list of facts, the attention panel's tasks. The rows run to the card's edge. */
export const ListCard = ({
  children,
  className,
  label,
}: {
  children: ReactNode;
  className?: string;
  /* Names the list for assistive tech when no heading beside it does. */
  label?: string;
}) => (
  <ul
    aria-label={label}
    className={cardClasses(cx("m-0 list-none divide-y divide-cv-hairline overflow-hidden p-0", className))}
  >
    {children}
  </ul>
);

interface ListRowProps {
  className?: ClassValue;
  /* A mark at the row's start - a lock, a sign-out arrow. Decorative. */
  icon?: LucideIcon;
  /* The row's name. */
  label: ReactNode;
  /* A row that opens something: a route (`to`) or an action (`onClick`). Either draws
     the chevron at the row's end that says the row leads somewhere. */
  onClick?: () => void;
  to?: string;
  /* What the row is set to now, or a control that sets it - drawn at the row's end. */
  trailing?: ReactNode;
}

const rowClasses = "flex min-h-13.5 w-full items-center gap-3 px-3.5 text-start text-body text-cv-text";

/* One row of a `ListCard`. A row that leads somewhere is itself the link or button, so
   the whole row is the target; a row that only shows a value or holds a control is a
   plain line. */
export const ListRow = ({ className, icon: Icon, label, onClick, to, trailing }: ListRowProps) => {
  const content = (
    <>
      {Icon === undefined ? null : <Icon aria-hidden="true" className="size-4.5 shrink-0" />}
      <span className="min-w-0 flex-1 truncate font-medium">{label}</span>
      {trailing === undefined ? null : <span className="shrink-0 text-label text-cv-text-muted">{trailing}</span>}
      {to === undefined && onClick === undefined ? null : (
        <ChevronLeft aria-hidden="true" className="size-4.5 shrink-0 text-cv-text-muted" />
      )}
    </>
  );
  const interactive = cx(rowClasses, "transition-colors hover:bg-cv-surface-muted", className);

  return (
    <li>
      {to !== undefined ? (
        <Link className={interactive} to={to}>
          {content}
        </Link>
      ) : onClick !== undefined ? (
        <button className={interactive} onClick={onClick} type="button">
          {content}
        </button>
      ) : (
        <div className={cx(rowClasses, className)}>{content}</div>
      )}
    </li>
  );
};
