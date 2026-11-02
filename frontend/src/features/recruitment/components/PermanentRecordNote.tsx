import { Lock } from "lucide-react";
import type { ReactNode } from "react";

/* The one thing every submission form says before it records: what is written cannot be
   taken back. A tinted block under a lock rather than a warning callout - recording a
   submission is the expected step, and the note states a property of the record, not a
   danger. The internal submission of a Ready document and an external one both use it. */
export const PermanentRecordNote = ({ children }: { children: ReactNode }) => (
  <div className="flex items-start gap-3 rounded-control bg-cv-canvas px-3.5 py-3">
    <Lock aria-hidden="true" className="mt-0.5 size-icon-lg shrink-0 text-cv-text" />
    <div className="min-w-0">
      <p className="text-label font-bold text-cv-text">הרישום קבוע</p>
      <p className="text-support leading-relaxed text-cv-text-muted">{children}</p>
    </div>
  </div>
);
