import { Copy } from "lucide-react";
import { useState } from "react";

import type { ApplicationDetail } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Disclosure } from "@/ui/Disclosure";
import { surfaceClasses } from "@/ui/Surface";

/* The stored posting text, collapsed. One component because two screens need the same
   source under two different conclusions - the snapshot record on Job Detail, and the
   classification on the preparation screen - and a second copy of the same markup would
   let the posting be presented one way in one place and another way in the other.

   It stays collapsed everywhere. A posting is longer than anything around it, it is input
   rather than conclusion, and opening it is a deliberate act of checking. */
export const JobTextDisclosure = ({ detail, summary }: { detail: ApplicationDetail; summary: string }) => {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const jobText = typeof detail.latest_snapshot.job_text === "string" ? detail.latest_snapshot.job_text : "";

  if (jobText.trim() === "") {
    return <p className="text-support leading-6 text-cv-text-muted">תצלום המשרה לא כולל טקסט שמור.</p>;
  }

  const copyJobText = async () => {
    try {
      await navigator.clipboard.writeText(jobText);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  };

  return (
    <Disclosure summary={summary}>
      <div className="mb-2 flex items-center justify-end gap-2">
        <span aria-live="polite" className="text-support text-cv-text-muted">
          {copyState === "copied" ? "נוסח המשרה הועתק" : copyState === "failed" ? "לא ניתן להעתיק" : null}
        </span>
        <Button
          aria-label="העתקת נוסח המשרה"
          className="w-11 !px-0"
          onClick={() => void copyJobText()}
          title="העתקת נוסח המשרה"
          variant="ghost"
        >
          <Copy aria-hidden="true" className="size-5 shrink-0" />
        </Button>
      </div>
      {/* Backend-stored source text, in whatever language the posting was written in: it
          picks its own direction, and `whitespace-pre-wrap` keeps the posting's own line
          breaks rather than reflowing it into one block - the record stays byte-identical
          to what was captured, only its container is styled.

          Capped and scrollable - a full posting is longer than the analysis above it, and
          left unbounded it would push every action on the screen off the fold the moment
          the section is opened. The card spans the full width like its neighbours; only
          the text line inside is capped, so a source line does not stretch so wide that
          its own short, hard-wrapped lines read as empty gaps rather than paragraph
          breaks - capping the card itself just left a dead gap beside it. */}
      <blockquote
        className={surfaceClasses("max-h-96 overflow-y-auto bg-cv-surface-muted py-3 ps-4 pe-3 text-cv-text")}
        dir="auto"
      >
        <p className="max-w-[75ch] text-body leading-7 whitespace-pre-wrap">{jobText}</p>
      </blockquote>
    </Disclosure>
  );
};
