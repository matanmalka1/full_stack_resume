import type { ApplicationListItem } from "@/api/contracts";
import { StatusBadge } from "@/ui/StatusBadge";
import { recruitmentStatusLabel, recruitmentStatusTone } from "@/features/recruitment";
import { CompanyMark } from "./ApplicationIdentity";
import { ApplicationPreparationStatus } from "./ApplicationListStatuses";

/* One Application named the way the board names it, with no link of its own.

   It exists so a caller outside the board - the global search palette - can show a
   result without restating how a company, a role, and the two statuses are drawn. The
   board's own rows link from the company name; a result that is itself one control
   must not, so the identity is plain text here. */
export const ApplicationSummary = ({ item }: { item: ApplicationListItem }) => (
  <>
    <div className="flex min-w-0 items-center gap-3">
      <CompanyMark company={item.company} variant="row" />
      <div className="min-w-0">
        <p className="truncate font-semibold text-cv-text" dir="auto">
          {item.company}
        </p>
        <p className="truncate text-support text-cv-text-muted" dir="auto">
          {item.target_role}
        </p>
      </div>
    </div>

    <div className="flex shrink-0 items-center gap-2">
      <ApplicationPreparationStatus item={item} variant="pipeline" />
      <StatusBadge className="px-2 py-0.5" tone={recruitmentStatusTone(item.recruitment_status)}>
        {recruitmentStatusLabel(item.recruitment_status)}
      </StatusBadge>
    </div>
  </>
);
