import { FileText } from "lucide-react";

import type { WorkingDraft, WorkingDraftFacts } from "@/api/contracts";
import { Card } from "@/ui/Card";
import { SectionHeader } from "@/ui/SectionHeader";
import type { DraftClaimActions } from "../model/drafts.types";
import { DraftClaimList } from "./DraftClaimList";

interface DraftIdentityCardProps {
  actions: DraftClaimActions;
  draft: WorkingDraft;
  facts: WorkingDraftFacts | undefined;
}

/* The document's opening lines: the headline and the contact details. They come from the
   candidate's profile rather than from the selection plan, which is why they are their
   own card above the sections and why neither of them can be removed here. */
export const DraftIdentityCard = ({ actions, draft, facts }: DraftIdentityCardProps) => (
  <Card
    aria-labelledby="draft-structure-heading"
    className="flex flex-col gap-4 bg-cv-surface p-4 shadow-surface sm:p-5"
  >
    <SectionHeader
      actions={<span className="text-support text-cv-text-muted">מבוססים על הקשר המועמד</span>}
      align="center"
      gap="tight"
      headingId="draft-structure-heading"
      icon={FileText}
      iconPresentation="inline"
      title="כותרת ופרטי קשר"
    />

    <DraftClaimList
      actions={actions}
      claims={[draft.outline.headline, ...draft.outline.contacts]}
      draft={draft}
      emptyLabel="אין כרגע כותרת ופרטי קשר בטיוטה."
      facts={facts}
    />
  </Card>
);
