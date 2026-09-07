import type { ReactNode } from "react";

import type { DraftClaim, WorkingDraft, WorkingDraftFacts } from "@/api/contracts";
import type { DraftClaimActions } from "../drafts.types";
import { linkedFacts, removability } from "../model/draftClaims";
import { DraftClaimRow } from "./DraftClaimRow";

interface DraftClaimListProps {
  actions: DraftClaimActions;
  claims: DraftClaim[];
  draft: WorkingDraft;
  /* Built only for a `pending` line, which is the only line that can be resolved into a
     fact. Passed as a function so the sections that have that context supply it and the
     identity card, which has no section to attach a fact to, simply does not. */
  factResolution?: (claim: DraftClaim) => ReactNode;
  facts: WorkingDraftFacts | undefined;
  /* Rendered instead of the list when the outline names no claims here. */
  emptyLabel: string;
}

/* One run of claims as a list of rows.

   It is where the per-claim answers are worked out - which facts back a line, and which
   command would remove it - so both are decided by one policy in one place rather than by
   each row for itself. The rows below it draw what they are given. */
export const DraftClaimList = ({
  actions,
  claims,
  draft,
  emptyLabel,
  factResolution,
  facts,
}: DraftClaimListProps): ReactNode => {
  if (claims.length === 0) {
    return <p className="text-support leading-6 text-cv-text-muted">{emptyLabel}</p>;
  }

  return (
    <ul className="flex flex-col divide-y divide-cv-border">
      {claims.map((claim) => (
        <DraftClaimRow
          actions={actions}
          claim={claim}
          facts={linkedFacts(claim, facts)}
          factResolution={claim.claim_type === "pending" ? factResolution?.(claim) : undefined}
          key={claim.claim_id}
          removal={removability(claim, draft, facts)}
        />
      ))}
    </ul>
  );
};
