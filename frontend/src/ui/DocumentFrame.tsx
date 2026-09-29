import { Minus, MoveHorizontal, Plus } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/ui/Button";
import { cx } from "@/ui/cx";

const PAGE_WIDTH_PX = 794;
const PAGE_HEIGHT_PX = 1123;
const MIN_ZOOM_PERCENT = 25;
const MAX_ZOOM_PERCENT = 200;
const ZOOM_STEP_PERCENT = 10;

/* The canvas pads the page on every side; the fit calculation reads the padded
   viewport's content box, so the padding never pushes the page into a scrollbar. */
const CANVAS_PADDING_PX = 16;

interface DocumentFrameProps {
  /* The document behind the frame is being replaced: the page dims until it loads. */
  busy?: boolean;
  className?: string;
  onLoad?: () => void;
  src: string;
  title: string;
}

type ZoomMode = "fit" | "manual";

const clampZoom = (zoom: number): number => Math.min(MAX_ZOOM_PERCENT, Math.max(MIN_ZOOM_PERCENT, zoom));
const fitZoomForWidth = (width: number): number =>
  Math.min(100, Math.max(MIN_ZOOM_PERCENT, (width / PAGE_WIDTH_PX) * 100));

/* `compact` keeps the button 32px tall; its inline padding leaves exactly one icon's
   width inside the fixed step width. */
const zoomStepClasses = "w-9";

/* The rendered CV remains a fixed 794x1123 A4 page. This component changes only the
   browser presentation around that page: the iframe always receives its native layout
   dimensions, while a transform and an explicitly-sized canvas provide zoom and
   scrollbars without reflowing the document or changing the rendered artifact.

   It owns its whole presentation - toolbar, canvas, and the page on it - so every
   screen that shows a CV shows the same object, and no caller wraps the toolbar in a
   surface of its own. */
export const DocumentFrame = ({ busy = false, className, onLoad, src, title }: DocumentFrameProps) => {
  const viewportRef = useRef<HTMLElement>(null);
  const [fitZoom, setFitZoom] = useState(100);
  const [manualZoom, setManualZoom] = useState(100);
  const [zoomMode, setZoomMode] = useState<ZoomMode>("fit");

  useLayoutEffect(() => {
    const node = viewportRef.current;
    if (node === null || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? 0;
      if (width > 0) setFitZoom(fitZoomForWidth(width));
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const zoom = zoomMode === "fit" ? fitZoom : manualZoom;
  const scale = zoom / 100;
  const shownZoom = Math.round(zoom);

  const selectManualZoom = (nextZoom: number) => {
    setManualZoom(clampZoom(nextZoom));
    setZoomMode("manual");
  };

  return (
    <div
      className={cx(
        "flex min-w-0 flex-col overflow-hidden rounded-surface border border-cv-border bg-cv-canvas",
        className,
      )}
    >
      <div
        aria-label="בקרות זום למסמך"
        className="flex flex-wrap items-center justify-between gap-2 border-b border-cv-border bg-cv-surface px-3 py-2"
        role="toolbar"
      >
        <div className="inline-flex items-stretch overflow-hidden rounded-control border border-cv-border bg-cv-surface">
          <Button
            aria-label="הקטנת המסמך"
            className={zoomStepClasses}
            disabled={zoom <= MIN_ZOOM_PERCENT}
            onClick={() => selectManualZoom(zoom - ZOOM_STEP_PERCENT)}
            size="compact"
            variant="ghost"
          >
            <Minus aria-hidden="true" className="size-icon-md" />
          </Button>
          <output
            aria-live="polite"
            className="flex min-w-14 items-center justify-center border-x border-cv-border px-2 text-support font-semibold tabular-nums text-cv-text"
          >
            {shownZoom}%
          </output>
          <Button
            aria-label="הגדלת המסמך"
            className={zoomStepClasses}
            disabled={zoom >= MAX_ZOOM_PERCENT}
            onClick={() => selectManualZoom(zoom + ZOOM_STEP_PERCENT)}
            size="compact"
            variant="ghost"
          >
            <Plus aria-hidden="true" className="size-icon-md" />
          </Button>
        </div>

        <div className="flex items-center gap-1">
          <Button
            aria-pressed={zoomMode === "manual" && manualZoom === 100}
            className={cx(zoomMode === "manual" && manualZoom === 100 && "bg-cv-accent-soft")}
            onClick={() => selectManualZoom(100)}
            size="compact"
            variant="ghost"
          >
            100%
          </Button>
          <Button
            aria-pressed={zoomMode === "fit"}
            className={cx(zoomMode === "fit" && "bg-cv-accent-soft")}
            onClick={() => setZoomMode("fit")}
            size="compact"
            variant="ghost"
          >
            <MoveHorizontal aria-hidden="true" className="size-icon-md" />
            התאמה לרוחב
          </Button>
        </div>
      </div>

      <section
        aria-busy={busy || undefined}
        aria-label="מסמך קורות החיים — ניתן לגלול"
        className="w-full overflow-auto overscroll-contain [scrollbar-gutter:stable]"
        dir="ltr"
        ref={viewportRef}
        style={{
          height: PAGE_HEIGHT_PX * scale + CANVAS_PADDING_PX * 2,
          maxHeight: "75vh",
          padding: CANVAS_PADDING_PX,
        }}
        /* A scrollable document must be focusable for arrow/PageUp/PageDown navigation.
           It is intentionally not an application control, so no interactive ARIA role
           describes it more accurately than its named section semantics. */
        // oxlint-disable-next-line jsx-a11y/no-noninteractive-tabindex
        tabIndex={0}
      >
        <div
          className={cx(
            "relative mx-auto shrink-0 bg-cv-surface shadow-document ring-1 ring-cv-hairline transition-opacity duration-200",
            busy && "opacity-60",
          )}
          style={{ height: PAGE_HEIGHT_PX * scale, width: PAGE_WIDTH_PX * scale }}
        >
          <iframe
            className="absolute left-0 top-0 border-0 bg-cv-surface"
            onLoad={onLoad}
            sandbox=""
            src={src}
            style={{
              height: PAGE_HEIGHT_PX,
              transform: `scale(${scale})`,
              transformOrigin: "top left",
              width: PAGE_WIDTH_PX,
            }}
            title={title}
          />
        </div>
      </section>
    </div>
  );
};
