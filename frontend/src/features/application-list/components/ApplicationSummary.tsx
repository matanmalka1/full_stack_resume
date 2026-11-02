import type { ReactNode } from "react";

import type { ApplicationListItem } from "@/api/contracts";
import { InitialTile } from "@/ui/InitialTile";
import { StatusBadge } from "@/ui/StatusBadge";
import { applicationAttention } from "../model/applicationListPresentation";
import { ApplicationStageBadge } from "./ApplicationListStatuses";

/* One Application named the way the board names it, with no link of its own: the
   employer's initial, the role, the employer, and one chip - "needs attention" when the
   projection holds a reason, its recruitment stage otherwise.

   It exists so a caller outside the board - the quick search - can show a result without
   restating how an Application is drawn. A result that is itself one control must not
   hold a link, so everything here is plain text. `mark` lets the caller draw the matched
   part of the role and the employer. */
const plain = (text: string): ReactNode => text;

export const ApplicationSummary = ({
  item,
  mark = plain,
}: {
  item: ApplicationListItem;
  mark?: (text: string) => ReactNode;
}) => (
  <>
    <InitialTile
      className="max-lg:size-10 max-lg:text-heading-sm lg:size-9 lg:rounded-control-sm lg:border lg:border-cv-hairline lg:bg-cv-surface lg:text-body"
      name={item.company}
    />
    <span className="min-w-0 flex-1">
      <span className="block truncate text-body font-bold text-cv-text">
        <bdi>{mark(item.target_role)}</bdi>
      </span>
      <span className="block truncate text-support text-cv-text-muted">
        <span dir="auto">{mark(item.company)}</span> · מועמדות
      </span>
    </span>
    {applicationAttention(item) === null ? (
      <ApplicationStageBadge className="px-2 py-0.5" item={item} />
    ) : (
      <StatusBadge icon={false} className="px-2 py-0.5" tone="progress" variant="solid">
        דורש טיפול
      </StatusBadge>
    )}
  </>
);
