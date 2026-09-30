import type { ReactNode } from "react";

import type { JobAnalysisRecord } from "@/api/contracts";
import { DateTime } from "@/ui/DateTime";

export const AnalysisHeader = ({ children, record }: { children?: ReactNode; record: JobAnalysisRecord | null }) => (
  <div className="border-b border-cv-border pb-4">
    <div className="min-w-0">
      <h2 className="text-heading-sm font-bold text-cv-text" id="analysis-heading">
        ניתוח המשרה
      </h2>
      {record === null ? null : (
        <p className="mt-1 text-support text-cv-text-muted" dir="rtl">
          נותחה ב־
          <DateTime value={record.created_at} />
        </p>
      )}
    </div>
    {children}
  </div>
);
