import type { ApplicationDetail } from "../../api/contracts";
import { Disclosure } from "../../ui/Disclosure";

/* The stored posting text, collapsed. One component because two screens need the same
   source under two different conclusions - the snapshot record on Job Detail, and the
   classification on the preparation screen - and a second copy of the same markup would
   let the posting be presented one way in one place and another way in the other.

   It stays collapsed everywhere. A posting is longer than anything around it, it is input
   rather than conclusion, and opening it is a deliberate act of checking. */
export const JobTextDisclosure = ({ detail, summary }: { detail: ApplicationDetail; summary: string }) => {
  const jobText = typeof detail.latest_snapshot.job_text === "string" ? detail.latest_snapshot.job_text.trim() : "";

  if (jobText === "") {
    return <p className="text-support leading-6 text-cv-text-muted">תצלום המשרה לא כולל טקסט שמור.</p>;
  }

  return (
    <Disclosure summary={summary}>
      {/* Backend-stored source text, in whatever language the posting was written in: it
          picks its own direction, and `whitespace-pre-wrap` keeps the posting's own line
          breaks rather than reflowing it into one block.

          Capped and scrollable - a full posting is longer than the analysis above it, and
          left unbounded it would push every action on the screen off the fold the moment
          the section is opened. */}
      <p
        className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded-control bg-cv-surface-muted p-3 leading-6 text-cv-text"
        dir="auto"
      >
        {jobText}
      </p>
    </Disclosure>
  );
};
