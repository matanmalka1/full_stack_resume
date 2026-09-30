import { Check, CloudAlert, CloudUpload, History } from "lucide-react";

import { LiveRegion } from "@/ui/LiveRegion";
import { cx } from "@/ui/cx";
import { type Tone, toneTextClasses } from "@/ui/tone";
import type { IntakeDraftStatus as Status } from "../hooks/useApplicationIntakeDraft";

const labels: Record<Status, string> = {
  idle: "הטופס נשמר אוטומטית בדפדפן הזה עד ליצירת המועמדות.",
  restored: "פרטים שהוזנו קודם שוחזרו מהדפדפן הזה.",
  saving: "שומר את הפרטים בדפדפן הזה…",
  saved: "הפרטים נשמרו בדפדפן הזה עד ליצירת המועמדות.",
  failed: "לא ניתן לשמור את הפרטים בדפדפן. אין לסגור את העמוד לפני יצירת המועמדות.",
};

const statusTones: Record<Status, Tone> = {
  idle: "neutral",
  restored: "info",
  saving: "neutral",
  saved: "success",
  failed: "blocker",
};

export const IntakeDraftStatus = ({ status }: { status: Status }) => {
  const Icon =
    status === "failed" ? CloudAlert : status === "saved" ? Check : status === "restored" ? History : CloudUpload;

  return (
    <div className="flex items-center gap-2 text-support text-cv-text-muted">
      <Icon aria-hidden="true" className={cx("size-icon-md shrink-0", toneTextClasses[statusTones[status]])} />
      <LiveRegion visuallyHidden={false}>{labels[status]}</LiveRegion>
    </div>
  );
};
