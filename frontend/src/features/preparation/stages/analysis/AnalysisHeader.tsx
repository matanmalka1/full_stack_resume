import type { ReactNode } from "react";

import type { JobAnalysisRecord } from "@/api/contracts";
import { formatDateTime } from "@/utils/formatDateTime";

export const AnalysisHeader = ({ children, record }: { children?: ReactNode; record: JobAnalysisRecord | null }) => (
  <div className="border-b border-cv-border pb-4">
    <div className="min-w-0">
      <h2 className="text-heading-sm font-bold text-cv-text" id="analysis-heading">
        ניתוח המשרה
      </h2>
      {record === null ? null : (
        <p className="mt-1 text-support text-cv-text-muted" dir="rtl">
          {/* The model is the provider record's, listed under "תוצרי המנוע". */}
          נותחה ב־<bdi>{formatDateTime(record.created_at)}</bdi>
          {record.version_number <= 1 ? null : ` · ניתוח מס' ${record.version_number}`}
        </p>
      )}
    </div>
    {children}
  </div>
);
