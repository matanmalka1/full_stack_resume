import { Minus, Plus } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";

import { Button } from "@/ui/Button";
import { cx } from "@/ui/cx";

const PAGE_WIDTH_PX = 794;
const PAGE_HEIGHT_PX = 1123;
const MIN_ZOOM_PERCENT = 25;
const MAX_ZOOM_PERCENT = 200;
const ZOOM_STEP_PERCENT = 10;

interface DocumentFrameProps {
  className?: string;
  frameClassName?: string;
  onLoad?: () => void;
  src: string;
  title: string;
}

type ZoomMode = "fit" | "manual";

const clampZoom = (zoom: number): number => Math.min(MAX_ZOOM_PERCENT, Math.max(MIN_ZOOM_PERCENT, zoom));
const fitZoomForWidth = (width: number): number =>
  Math.min(100, Math.max(MIN_ZOOM_PERCENT, (width / PAGE_WIDTH_PX) * 100));

/* The rendered CV remains a fixed 794x1123 A4 page. This component changes only the
   browser presentation around that page: the iframe always receives its native layout
   dimensions, while a transform and an explicitly-sized canvas provide zoom and
   scrollbars without reflowing the document or changing the rendered artifact. */
export const DocumentFrame = ({ className, frameClassName, onLoad, src, title }: DocumentFrameProps) => {
  const viewportRef = useRef<HTMLDivElement>(null);
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
    <div className={cx("flex min-w-0 flex-col gap-3", className)}>
      <div aria-label="בקרות זום למסמך" className="flex flex-wrap items-center gap-2" role="toolbar">
        <Button
          aria-label="הקטנת המסמך"
          disabled={zoom <= MIN_ZOOM_PERCENT}
          onClick={() => selectManualZoom(zoom - ZOOM_STEP_PERCENT)}
          size="icon"
          variant="secondary"
        >
          <Minus aria-hidden="true" className="size-icon-md" />
        </Button>
        <output aria-live="polite" className="min-w-14 text-center text-support tabular-nums text-cv-text">
          {shownZoom}%
        </output>
        <Button
          aria-label="הגדלת המסמך"
          disabled={zoom >= MAX_ZOOM_PERCENT}
          onClick={() => selectManualZoom(zoom + ZOOM_STEP_PERCENT)}
          size="icon"
          variant="secondary"
        >
          <Plus aria-hidden="true" className="size-icon-md" />
        </Button>
        <Button onClick={() => selectManualZoom(100)} size="compact" variant="secondary">
          100%
        </Button>
        <Button aria-pressed={zoomMode === "fit"} onClick={() => setZoomMode("fit")} size="compact" variant="secondary">
          התאמה לרוחב
        </Button>
      </div>

      <div
        aria-label="מסמך קורות החיים — ניתן לגלול"
        className="w-full overflow-auto overscroll-contain"
        dir="ltr"
        ref={viewportRef}
        role="region"
        style={{ height: PAGE_HEIGHT_PX * scale, maxHeight: "75vh" }}
        tabIndex={0}
      >
        <div
          className="relative mx-auto shrink-0"
          style={{ height: PAGE_HEIGHT_PX * scale, width: PAGE_WIDTH_PX * scale }}
        >
          <iframe
            className={cx(
              "absolute left-0 top-0 rounded-control border border-cv-border bg-cv-surface",
              frameClassName,
            )}
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
      </div>
    </div>
  );
};
