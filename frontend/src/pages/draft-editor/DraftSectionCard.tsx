import { Layers3, RefreshCw } from "lucide-react";

import type { ApplicationDetail, DraftClaim, WorkingDraft, WorkingDraftFacts } from "../../api/contracts";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { ClaimFactResolution } from "./ClaimFactResolution";
import { DraftClaimCard } from "./DraftClaimCard";

type DraftOutlineSection = WorkingDraft["outline"]["sections"][number];

/* The five props every `DraftClaimCard` on this screen is given, bundled once: the
   editor has one draft, one facts read, and one blur/edit/regenerate/remove policy for
   every claim on it, whichever section the claim happens to sit in. */
export interface ClaimHandlers {
  draft: WorkingDraft;
  facts: WorkingDraftFacts | undefined;
  onBlur: () => void;
  onEdit: (claim: DraftClaim, text: string) => void;
  onRegenerate: (claim: DraftClaim) => void;
  onRemove: (claim: DraftClaim) => void;
  unsaved: boolean;
}

interface DraftSectionCardProps {
  applicationId: string;
  claimHandlers: ClaimHandlers;
  detail: ApplicationDetail | undefined;
  onRegenerateSection: () => void;
  regenerationDisabled: boolean;
  section: DraftOutlineSection;
  sectionIndex: number;
}

/* A.4 frame 3: one section of the draft outline - its heading, its regenerate action,
   and the claims in it. Isolated from `DraftEditorPage` so the `claims.length === 0`
   branch and a section's own resolution wiring can be read, and tested, without the
   whole editor around them. */
export const DraftSectionCard = ({
  applicationId,
  claimHandlers,
  detail,
  onRegenerateSection,
  regenerationDisabled,
  section,
  sectionIndex,
}: DraftSectionCardProps) => (
  <Card
    aria-labelledby={`draft-section-${sectionIndex}`}
    className="flex flex-col gap-2 bg-cv-surface p-4 shadow-surface sm:p-5"
  >
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-cv-border pb-3">
      <div className="flex min-w-0 items-center gap-2">
        <Layers3 aria-hidden="true" className="size-4 shrink-0 text-cv-accent" />
        <h3 className="truncate text-heading-sm font-bold text-cv-text" dir="auto" id={`draft-section-${sectionIndex}`}>
          {section.name}
        </h3>
        <span className="shrink-0 text-support text-cv-text-muted">{section.claims.length} שורות</span>
      </div>
      <Button disabled={regenerationDisabled} onClick={onRegenerateSection} variant="secondary">
        <RefreshCw aria-hidden="true" className="size-4" />
        יצירה מחדש של הפרק
      </Button>
    </div>
    {section.claims.length === 0 ? (
      <p className="text-support leading-6 text-cv-text-muted">אין כרגע שורות בסעיף הזה.</p>
    ) : (
      <ul className="flex flex-col divide-y divide-cv-border">
        {section.claims.map((claim) => (
          <DraftClaimCard
            {...claimHandlers}
            claim={claim}
            factResolution={
              <ClaimFactResolution
                analysisId={detail?.active_analysis_id ?? null}
                applicationId={applicationId}
                claim={claim}
                draft={claimHandlers.draft}
                language={claimHandlers.facts?.language ?? detail?.application.language ?? "en"}
                profile={detail?.application.profile ?? null}
                section={section.name}
              />
            }
            key={claim.claim_id}
          />
        ))}
      </ul>
    )}
  </Card>
);
