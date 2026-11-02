import { Check, CloudAlert, CloudUpload, History } from "lucide-react";

import { LiveRegion } from "@/ui/LiveRegion";
import { cx } from "@/ui/cx";
import type { IntakeDraftStatus as Status } from "../hooks/useApplicationIntakeDraft";

/* The form is kept in this browser until the Application is created, and this line says
   where that stands in a few words - the design's quiet "saved" mark, not a paragraph. A
   failure keeps its warning: the reader must not close the page then. */
const labels: Record<Status, string> = {
  idle: "הטיוטה נשמרת בדפדפן",
  restored: "הטיוטה שוחזרה מהדפדפן",
  saving: "שומר את הטיוטה…",
  saved: "הטיוטה נשמרה",
  failed: "לא ניתן לשמור את הטיוטה בדפדפן - אין לסגור את העמוד",
};

export const IntakeDraftStatus = ({ className, status }: { className?: string; status: Status }) => {
  const Icon =
    status === "failed" ? CloudAlert : status === "saved" ? Check : status === "restored" ? History : CloudUpload;

  return (
    <div
      className={cx(
        "flex items-center gap-1.5 text-caption",
        status === "failed" ? "font-bold text-cv-blocker" : "text-cv-text-muted",
        className,
      )}
    >
      <Icon aria-hidden="true" className="size-3.5 shrink-0" />
      <LiveRegion visuallyHidden={false}>{labels[status]}</LiveRegion>
    </div>
  );
};
