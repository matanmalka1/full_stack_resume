import type { ReactNode } from "react";

import { ChevronLeft } from "lucide-react";
import { Link } from "react-router-dom";

import { cx } from "./cx";

export interface BreadcrumbItem {
  dir?: "auto" | "ltr" | "rtl";
  label: ReactNode;
  to?: string;
}

interface BreadcrumbsProps {
  items: readonly BreadcrumbItem[];
}

/* Route hierarchy, separate from the workflow landmark: ancestors are destinations and
   the final item is the page being read. The list may wrap on a narrow viewport so no
   navigable level disappears merely because a company or role has a long name. */
export const Breadcrumbs = ({ items }: BreadcrumbsProps) => (
  <nav aria-label="פירורי לחם">
    <ol className="flex min-w-0 flex-wrap items-center gap-y-1 text-support">
      {items.map((item, index) => {
        const current = index === items.length - 1;

        return (
          <li className="flex max-w-full shrink-0 items-center" key={`${index}:${item.to ?? "current"}`}>
            {index === 0 ? null : (
              <ChevronLeft aria-hidden="true" className="mx-1 size-4 shrink-0 text-cv-text-muted" />
            )}
            {current ? (
              <span
                aria-current="page"
                className="max-w-[min(28rem,70vw)] truncate px-1 font-semibold text-cv-text"
                dir={item.dir}
              >
                {item.label}
              </span>
            ) : item.to === undefined ? (
              <span className="px-1 text-cv-text-muted" dir={item.dir}>
                {item.label}
              </span>
            ) : (
              <Link
                className={cx(
                  "inline-flex min-h-11 max-w-[min(28rem,70vw)] items-center truncate rounded-control px-1",
                  "font-semibold text-cv-text-muted transition-colors duration-200 hover:text-cv-text",
                )}
                dir={item.dir}
                to={item.to}
              >
                {item.label}
              </Link>
            )}
          </li>
        );
      })}
    </ol>
  </nav>
);
