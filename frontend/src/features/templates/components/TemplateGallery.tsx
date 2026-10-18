import { Check, Columns2 } from "lucide-react";

import {
  type PreviewTemplate,
  TRACK_TEMPLATE_DESCRIPTION,
  TRACK_TEMPLATE_LABEL,
  type TemplateName,
  type TemplateOption,
} from "@/api/templates";
import { cx } from "@/ui/cx";

/* The rendered page is a fixed A4 of 794x1123 CSS pixels; a thumbnail is that page
   scaled down, never a reflowed small copy, so it shows the layout the PDF will have. */
const PAGE_WIDTH_PX = 794;
const PAGE_HEIGHT_PX = 1123;
const THUMBNAIL_SCALE = 0.2;

interface TemplateGalleryProps {
  disabled?: boolean;
  /* Names the radio group, for a screen that shows more than one. */
  name: string;
  onChange: (template: TemplateName | null) => void;
  options: readonly TemplateOption[];
  /* The page each card frames: the user's own CV in the editor, the sample in Settings. */
  previewSrc: (template: PreviewTemplate) => string;
  value: TemplateName | null;
}

/* One radio per template, each with what it looks like. A thumbnail is a sandboxed frame
   (no scripts, no same origin), out of the tab order and hidden from assistive tech: the
   radio and its name are the control, the picture only shows it. */
export const TemplateGallery = ({ disabled = false, name, onChange, options, previewSrc, value }: TemplateGalleryProps) => {
  const cards: { columns: number; description: string; id: TemplateName | null; label: string; preview: PreviewTemplate }[] = [
    { columns: 1, description: TRACK_TEMPLATE_DESCRIPTION, id: null, label: TRACK_TEMPLATE_LABEL, preview: "track" },
    ...options.map((option) => ({ ...option, preview: option.id })),
  ];

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(10.5rem,1fr))] gap-field-gap" role="radiogroup">
      {cards.map((card) => {
        const selected = card.id === value;
        return (
          <label
            className={cx(
              "group flex cursor-pointer flex-col gap-2 rounded-surface border bg-cv-surface p-2 transition-colors",
              "has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-cv-accent",
              selected ? "border-cv-accent ring-1 ring-cv-accent" : "border-cv-border hover:border-cv-border-strong",
              disabled && "cursor-not-allowed opacity-60",
            )}
            key={card.preview}
          >
            <input
              checked={selected}
              className="sr-only"
              disabled={disabled}
              name={name}
              onChange={() => onChange(card.id)}
              type="radio"
              value={card.preview}
            />
            <div
              className="relative mx-auto overflow-hidden bg-cv-surface shadow-document ring-1 ring-cv-hairline"
              dir="ltr"
              style={{ height: PAGE_HEIGHT_PX * THUMBNAIL_SCALE, width: PAGE_WIDTH_PX * THUMBNAIL_SCALE }}
            >
              <iframe
                aria-hidden="true"
                className="pointer-events-none absolute top-0 left-0 origin-top-left border-0"
                loading="lazy"
                sandbox=""
                src={previewSrc(card.preview)}
                style={{ height: PAGE_HEIGHT_PX, transform: `scale(${THUMBNAIL_SCALE})`, width: PAGE_WIDTH_PX }}
                tabIndex={-1}
                title={`תצוגה מקדימה: ${card.label}`}
              />
            </div>
            <span className="flex items-center gap-1.5 text-support font-semibold text-cv-text">
              {selected ? <Check aria-hidden="true" className="size-icon-sm shrink-0 text-cv-accent" /> : null}
              <span dir="auto">{card.label}</span>
            </span>
            <span className="text-caption leading-5 text-cv-text-muted">{card.description}</span>
            {card.columns > 1 ? (
              <span className="inline-flex items-center gap-1 text-caption text-cv-text-muted">
                <Columns2 aria-hidden="true" className="size-icon-sm shrink-0" />
                שתי עמודות: חלק ממערכות ה־ATS קוראות אותן פחות טוב
              </span>
            ) : null}
          </label>
        );
      })}
    </div>
  );
};
