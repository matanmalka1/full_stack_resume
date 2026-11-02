import { ChevronLeft } from "lucide-react";
import { type ReactNode, type SelectHTMLAttributes, useId } from "react";

import { CheckboxBox } from "@/ui/Checkbox";
import { cx } from "@/ui/cx";
import { cardClasses } from "@/ui/surface";

/* One area of Settings. A phone reads it as a settings list does: a small muted name over
   a rounded group. A wide screen gives the name and a line of what the area holds a
   column of their own beside the group, and a rule between areas. */
export const SettingsSection = ({
  children,
  className,
  description,
  divided = true,
  title,
}: {
  children: ReactNode;
  className?: string;
  description?: ReactNode;
  /* Draws the wide screen's rule under the area; the last area has nothing below it. */
  divided?: boolean;
  title: ReactNode;
}) => {
  const headingId = useId();

  return (
    <section
      aria-labelledby={headingId}
      className={cx(
        "flex flex-col gap-2 lg:flex-row lg:flex-wrap lg:gap-x-8 lg:gap-y-4",
        divided && "lg:border-b lg:border-cv-border lg:pb-6",
        className,
      )}
    >
      <div className="px-1 lg:flex-[1_1_13.75rem] lg:px-0">
        <h2
          className="text-support font-bold text-cv-text-muted lg:text-heading-sm lg:font-extrabold lg:text-cv-text"
          id={headingId}
        >
          {title}
        </h2>
        {description === undefined ? null : (
          <p className="mt-1 text-label text-cv-text-muted max-lg:hidden">{description}</p>
        )}
      </div>
      <div className="min-w-0 lg:flex-[2_1_23.75rem]">{children}</div>
    </section>
  );
};

/* The group a section's rows sit in: the design's card, rows divided by hairlines. */
export const SettingsGroup = ({ children, className }: { children: ReactNode; className?: string }) => (
  <div className={cardClasses(cx("divide-y divide-cv-hairline overflow-hidden", className))}>{children}</div>
);

const rowClasses = "flex min-h-13.5 items-center gap-3 px-3.5 lg:min-h-0 lg:px-4 lg:py-3.5";
const rowLabelClasses = "min-w-0 flex-1 text-body font-medium text-cv-text lg:text-label";

/* A setting chosen from a list. On a phone the row reads as a list row - the name, the
   current value muted at its end and a chevron - and a tap opens the system's own picker.
   A wide screen draws the select as the compact bordered control the design gives it. */
export const SettingsSelectRow = ({
  children,
  label,
  ...select
}: SelectHTMLAttributes<HTMLSelectElement> & { label: ReactNode }) => {
  const id = useId();

  return (
    <div className={rowClasses}>
      <label className={rowLabelClasses} htmlFor={id}>
        {label}
      </label>
      <span className="relative flex min-w-0 shrink items-center">
        <select
          className={cx(
            "min-w-0 cursor-pointer truncate bg-transparent text-label text-cv-text-muted max-lg:min-h-13.5 max-lg:appearance-none max-lg:pe-6 max-lg:text-end",
            "lg:h-10 lg:rounded-control-sm lg:border lg:border-cv-field-border lg:bg-cv-field-background lg:px-2.5 lg:text-cv-text lg:hover:border-cv-border-strong",
          )}
          id={id}
          {...select}
        >
          {children}
        </select>
        <ChevronLeft
          aria-hidden="true"
          className="pointer-events-none absolute end-0 size-4.5 text-cv-text-muted lg:hidden"
        />
      </span>
    </div>
  );
};

/* An on/off setting, drawn as the app's one checkbox; `role="switch"` announces it as
   on/off, and the row's name is its label. */
export const SettingsSwitchRow = ({
  checked,
  label,
  onChange,
}: {
  checked: boolean;
  label: ReactNode;
  onChange: (checked: boolean) => void;
}) => {
  const id = useId();

  return (
    <div className={rowClasses}>
      <label className={cx(rowLabelClasses, "cursor-pointer")} htmlFor={id}>
        {label}
      </label>
      <CheckboxBox
        aria-checked={checked}
        checked={checked}
        id={id}
        onChange={(event) => onChange(event.target.checked)}
        role="switch"
      />
    </div>
  );
};

/* A line in a group that only says something - why a setting cannot take effect. */
export const SettingsNoteRow = ({ children }: { children: ReactNode }) => (
  <p className="px-3.5 py-3 text-support leading-6 text-cv-text-muted lg:px-4">{children}</p>
);
