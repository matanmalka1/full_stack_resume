import type { ApplicationDetail } from "../api/contracts";
import { LtrText } from "../ui/LtrText";
import { SummaryList } from "../ui/SummaryList";
import { Disclosure } from "../ui/Disclosure";

/* The posting the analysis was run against, on the screen that reports the analysis.

   The verdict and its confidence were readable here long before the text they were drawn
   from was: "high fit, 98%" is a claim about a document the reader could not see, and the
   provenance block underneath named that document only by UUID. Judging whether the
   classification is right means reading what was classified, so the snapshot text is
   offered here rather than behind a route that does not exist - the projection already
   carries it as `latest_snapshot`, so this needs no request of its own.

   It stays collapsed. A posting is long, it is input rather than conclusion, and the
   analysis above is what the reader came for; opening it is a deliberate act of checking.

   `latest_snapshot` is the newest snapshot of the Application, which is the one the
   active analysis was run against whenever the analysis is the active one - the condition
   `classificationFromAnalysis` already requires before this panel is rendered at all. */
const dateFormat = new Intl.DateTimeFormat("he-IL", { dateStyle: "short", timeStyle: "short" });

/* An unparsable value is shown as it arrived rather than as "Invalid Date". */
const formatSnapshotDate = (value: string): string => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : dateFormat.format(parsed);
};

export const JobSnapshotPanel = ({ detail }: { detail: ApplicationDetail }) => {
  const snapshot = detail.latest_snapshot;
  const jobText = typeof snapshot.job_text === "string" ? snapshot.job_text.trim() : "";

  return (
    <section
      aria-labelledby="job-snapshot-heading"
      className="rounded-surface border border-cv-border p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-cv-border pb-4">
        <h2 className="text-body font-semibold text-cv-text" id="job-snapshot-heading">
          המשרה שנותחה
        </h2>
        <span className="text-support text-cv-text-muted">
          גרסה {snapshot.version_number}
        </span>
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
                        className="text-cv-accent underline underline-offset-2"
                        href={snapshot.source_url}
                        rel="noreferrer noopener"
                        target="_blank"
                      >
                        <LtrText>{snapshot.source_url}</LtrText>
                      </a>
                    ),
                  },
                ]),
            { term: "נלכד", value: formatSnapshotDate(snapshot.captured_at) },
          ]}
        />

        {jobText === "" ? (
          <p className="text-support leading-6 text-cv-text-muted">
            תצלום המשרה לא כולל טקסט שמור.
          </p>
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

      </div>
    </section>
  );
};
