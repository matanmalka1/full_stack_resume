import type { JobAnalysisRecord } from "@/api/contracts";
import { LtrText } from "@/ui/LtrText";
import { formatDateTime } from "@/utils/formatDateTime";

/* The panel's masthead: what this is, and which run produced it.

   The fit verdict is not repeated here. The step banner states it once, above this panel,
   with what it means; a badge here said the same level a second time a few centimetres
   lower. Provenance is the record's own - the model id and when it ran - rather than
   anything the analysis document claims about itself. */
export const AnalysisHeader = ({ record }: { record: JobAnalysisRecord | null }) => (
  <div className="border-b border-cv-border pb-4">
    <div className="min-w-0">
      <h2 className="text-heading-sm font-bold text-cv-text" id="analysis-heading">
        ניתוח המשרה
      </h2>
      {record === null ? null : (
        <p className="mt-1 text-support text-cv-text-muted" dir="rtl">
          נותחה באמצעות <LtrText>{record.model}</LtrText> · <bdi>{formatDateTime(record.created_at)}</bdi>
          {record.version_number <= 1 ? null : ` · ניתוח מס' ${record.version_number}`}
        </p>
      )}
    </div>
  </div>
);
