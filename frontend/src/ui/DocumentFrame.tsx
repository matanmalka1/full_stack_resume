import { useLayoutEffect, useRef, useState } from "react";

import { cx } from "@/ui/cx";

const PAGE_WIDTH_PX = 794;
const PAGE_HEIGHT_PX = 1123;

interface DocumentFrameProps {
  className?: string;
  frameClassName?: string;
  onLoad?: () => void;
  src: string;
  title: string;
}

/* The rendered CV is a fixed A4 page (794x1123px), not a responsive layout - shrinking the
   iframe element itself to the column width reflows that page at the wrong width and cuts
   every line mid-word, while a column wider than the page leaves bare space below it. The
   frame keeps its native A4 size and is scaled visually to fit the column instead, so the
   document always lays out the way the renderer built it, and the wrapper's height tracks
   the scaled page rather than a guessed constant. */
export const DocumentFrame = ({ className, frameClassName, onLoad, src, title }: DocumentFrameProps) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  useLayoutEffect(() => {
    const node = containerRef.current;
    if (node === null || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? 0;
      setScale(width > 0 ? Math.min(1, width / PAGE_WIDTH_PX) : 1);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      className={cx("flex justify-center overflow-hidden", className)}
      ref={containerRef}
      style={{ height: PAGE_HEIGHT_PX * scale }}
    >
      <iframe
        /* `shrink-0` is what makes the paragraph above true. The wrapper is a flex
           container, so without it the iframe - a flex item asked to be wider than the
           column - was shrunk by the flex algorithm to the column's width before the
           transform ever applied: the A4 page reflowed at ~450px and cut every line, and
           the scale then shrank that already-broken layout a second time. A transform
           changes what is painted, never the box the layout gave it. */
        className={cx("shrink-0 rounded-control border border-cv-border bg-cv-surface", frameClassName)}
        onLoad={onLoad}
        sandbox=""
        src={src}
        style={{
          height: PAGE_HEIGHT_PX,
          transform: `scale(${scale})`,
          transformOrigin: "top center",
          width: PAGE_WIDTH_PX,
        }}
        title={title}
      />
    </div>
  );
};
