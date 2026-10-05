import { ExternalLink } from "lucide-react";

import type { ApplicationDetail } from "@/api/contracts";
import { Card } from "@/ui/Card";
import { LtrText } from "@/ui/LtrText";
import { SectionHeader } from "@/ui/SectionHeader";
import { SummaryList } from "@/ui/SummaryList";
import { formatDateTime } from "@/utils/formatDateTime";
import { JobPostingUpdate } from "./JobPostingUpdate";
import { CopyableTextDisclosure } from "@/ui/CopyableTextDisclosure";
import { sourceHostname } from "../model/applicationPresentation";

/* The posting on Job Detail. The projection already carries `job_posting`, so the source
   remains readable before analysis and after the preparation workflow ends.

   The posting text itself uses the shared copyable disclosure, so
   the same source reads the same way under both conclusions.

   `job_posting` is the Application's one job text: edited in place, and locked once the
   Application has a Submission. */
export const JobPostingPanel = ({
  detail,
  operationLive,
}: {
  detail: ApplicationDetail;
  /* The host screen's answer to whether this Application's work is under way. */
  operationLive: boolean;
}) => {
  const posting = detail.job_posting;

  return (
    <Card aria-labelledby="job-posting-heading" className="rounded-surface bg-cv-surface p-4 shadow-surface sm:p-5">
      <SectionHeader
        align="center"
        gap="wide"
        headingId="job-posting-heading"
        headingSize="body"
        spacing="roomy"
        title="מודעת המשרה"
      />

      <JobPostingUpdate detail={detail} operationLive={operationLive} />

      <div className="mt-4 flex flex-col gap-4">
        <SummaryList
          items={[
            ...(posting.source_url == null
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
                        href={posting.source_url}
                        rel="noreferrer noopener"
                        target="_blank"
                        title={posting.source_url}
                      >
                        פתיחת מודעת המקור
                        <LtrText>({sourceHostname(posting.source_url) ?? "המקור השמור"})</LtrText>
                        <ExternalLink aria-hidden="true" className="size-icon-sm shrink-0" />
                      </a>
                    ),
                  },
                ]),
            { term: "עודכן", value: formatDateTime(posting.job_text_updated_at, "short") },
          ]}
        />

        <CopyableTextDisclosure
          emptyMessage="נוסח המשרה אינו זמין."
          label="נוסח המשרה"
          summary="הצגת נוסח המשרה השמור"
          text={posting.job_text}
        />
      </div>
    </Card>
  );
};
