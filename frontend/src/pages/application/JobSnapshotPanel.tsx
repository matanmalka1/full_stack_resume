import { ExternalLink } from "lucide-react";

import type { ApplicationDetail } from "../../api/contracts";
import { LtrText } from "../../ui/LtrText";
import { SummaryList } from "../../ui/SummaryList";
import { formatDateTime } from "../../ui/formatDateTime";
import { JobPostingUpdate } from "./JobPostingUpdate";
import { JobTextDisclosure } from "./JobTextDisclosure";

/* The active posting on Job Detail. The projection already carries `latest_snapshot`, so
   the source remains readable before analysis and after the preparation workflow ends.

   The posting text itself is `JobTextDisclosure`, shared with the preparation screen so
   the same source reads the same way under both conclusions.

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

  return (
    <section
      aria-labelledby="job-snapshot-heading"
      className="rounded-surface border border-cv-border bg-cv-surface p-4 shadow-surface sm:p-5"
    >
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

        <JobTextDisclosure detail={detail} summary="הצגת נוסח המשרה השמור" />

        <JobPostingUpdate detail={detail} />
      </div>
    </section>
  );
};
