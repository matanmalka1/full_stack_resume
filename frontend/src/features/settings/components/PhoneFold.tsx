import { ChevronLeft, type LucideIcon } from "lucide-react";
import { useId, useState } from "react";

import { cx } from "@/ui/cx";

/* A phone's Settings is a list of rows, each a door to one setting, rather than every
   control drawn open at once - eleven template thumbnails and a three-field password form
   made the screen a scroll of several thousand pixels. Below the large breakpoint a long
   section folds behind a row that names it and, where there is one, its current value;
   the row opens the section in place. A wide screen has the room, so the row is not drawn
   there and the section is always open.

   It folds in place rather than opening a sub-screen: a sub-screen would be a route of
   its own, and these sections are part of the one Settings form and its one save. */
export const usePhoneFold = () => {
  const [open, setOpen] = useState(false);
  const id = useId();

  return {
    /* For the folded section: hidden below the large breakpoint until opened. */
    panelProps: { className: open ? undefined : "max-lg:hidden", id },
    rowProps: { controls: id, onToggle: () => setOpen((current) => !current), open },
  };
};

export const PhoneFoldRow = ({
  controls,
  icon: Icon,
  label,
  onToggle,
  open,
  value,
}: {
  controls: string;
  icon?: LucideIcon;
  label: string;
  onToggle: () => void;
  open: boolean;
  value?: string;
}) => (
  <button
    aria-controls={controls}
    aria-expanded={open}
    className="flex min-h-12 w-full items-center gap-3 text-start text-body font-semibold text-cv-text lg:hidden"
    onClick={onToggle}
    type="button"
  >
    {Icon === undefined ? null : <Icon aria-hidden="true" className="size-icon-lg shrink-0" />}
    <span className="min-w-0 flex-1">{label}</span>
    {value === undefined ? null : (
      <span className="min-w-0 truncate text-support font-normal text-cv-text-muted" dir="auto">
        {value}
      </span>
    )}
    <ChevronLeft
      aria-hidden="true"
      className={cx("size-icon-md shrink-0 text-cv-text-muted transition-transform", open && "-rotate-90")}
    />
  </button>
);
