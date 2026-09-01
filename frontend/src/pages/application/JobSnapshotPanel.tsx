import { ExternalLink } from "lucide-react";

import type { ApplicationDetail } from "../../api/contracts";
import { LtrText } from "../../ui/LtrText";
import { Disclosure } from "../../ui/Disclosure";
import { SummaryList } from "../../ui/SummaryList";
import { formatDateTime } from "../../ui/formatDateTime";
import { JobPostingUpdate } from "./JobPostingUpdate";

/* The active posting on Job Detail. The projection already carries `latest_snapshot`, so
   the source remains readable before analysis and after the preparation workflow ends.

   It stays collapsed. A posting is long, it is input rather than conclusion, and the
   analysis above is what the reader came for; opening it is a deliberate act of checking.

   `latest_snapshot` is the newest immutable snapshot of the Application. */
const sourceHostname = (value: string): string => {
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return "המקור השמור";
  }
};

export const JobSnapshotPanel = ({ detail }: { detail: ApplicationDetail }) => {
  const snapshot = detail.latest_snapshot;
  const jobText = typeof snapshot.job_text === "string" ? snapshot.job_text.trim() : "";

  return (
    <section aria-labelledby="job-snapshot-heading">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-cv-border pb-4">
        <h2 className="text-body font-semibold text-cv-text" id="job-snapshot-heading">
          מודעת המשרה
        </h2>
        <span className="text-support text-cv-text-muted">גרסה {snapshot.version_number}</span>
      </div>

      <div className="mt-4 flex flex-col gap-4">
        <SummaryList
          items={[
            ...(snapshot.source_url == null
              ? []
              : [
                  {
                    term: "מקור",
                    /* The posting's own address, which is Latin text in a Hebrew shell and
                       must not be reordered. It opens in a new tab: the reader is checking
                       a source mid-decision, not leaving the workflow. */
                    value: (
                      <a
                        className="inline-flex max-w-full items-center gap-1.5 text-cv-accent hover:underline"
                        href={snapshot.source_url}
                        rel="noreferrer noopener"
                        target="_blank"
                        title={snapshot.source_url}
                      >
                        פתיחת מודעת המקור
                        <LtrText>({sourceHostname(snapshot.source_url)})</LtrText>
                        <ExternalLink aria-hidden="true" className="size-3.5 shrink-0" />
                      </a>
                    ),
                  },
                ]),
            { term: "נלכד", value: formatDateTime(snapshot.captured_at, "short") },
          ]}
        />

        {jobText === "" ? (
          <p className="text-support leading-6 text-cv-text-muted">תצלום המשרה לא כולל טקסט שמור.</p>
        ) : (
          <Disclosure summary="הצגת נוסח המשרה שנותח">
            {/* Backend-stored source text, in whatever language the posting was written
                in: it picks its own direction, and `whitespace-pre-wrap` keeps the
                posting's own line breaks rather than reflowing it into one block.

                Capped and scrollable - a full posting is longer than the analysis above
                it, and left unbounded it would push every action on this screen off the
                fold the moment the section is opened. */}
            <p
              className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded-control bg-cv-surface-muted p-3 leading-6 text-cv-text"
              dir="auto"
            >
              {jobText}
            </p>
          </Disclosure>
        )}

        <JobPostingUpdate detail={detail} />
      </div>
    </section>
  );
};
