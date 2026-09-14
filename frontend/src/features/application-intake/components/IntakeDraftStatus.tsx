import { Check, CloudAlert, CloudUpload, History } from "lucide-react";

import { LiveRegion } from "@/ui/LiveRegion";
import { cx } from "@/ui/cx";
import type { IntakeDraftStatus as Status } from "../hooks/useApplicationIntakeDraft";

const labels: Record<Status, string> = {
  idle: "הטופס נשמר אוטומטית בדפדפן הזה עד ליצירת המועמדות.",
  restored: "טיוטה קודמת שוחזרה מהדפדפן.",
  saving: "שומר טיוטה בדפדפן…",
  saved: "הטיוטה נשמרה בדפדפן.",
  failed: "לא ניתן לשמור את הטיוטה בדפדפן. אין לסגור את העמוד לפני השליחה.",
};

export const IntakeDraftStatus = ({ status }: { status: Status }) => {
  const Icon =
    status === "failed" ? CloudAlert : status === "saved" ? Check : status === "restored" ? History : CloudUpload;

  return (
    <div className="flex items-center gap-2 text-support text-cv-text-muted">
      <Icon
        aria-hidden="true"
        className={cx(
          "size-icon-md shrink-0",
          status === "failed"
            ? "text-cv-blocker"
            : status === "saved"
              ? "text-cv-success"
              : status === "restored"
                ? "text-cv-info"
                : "text-cv-text-muted",
        )}
      />
      <LiveRegion visuallyHidden={false}>{labels[status]}</LiveRegion>
    </div>
  );
};
