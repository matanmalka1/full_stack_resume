import type { DocumentFacts, EditableDocument } from "../model/drafts.types";
import type { ClaimFactContext, DraftClaimActions } from "../model/drafts.types";
import type { ClaimRequirements } from "../model/draftFit";
import { IDENTITY_PART, sectionPartId } from "../model/draftParts";
import { DraftIdentityCard } from "./DraftIdentityCard";
import { DraftSectionCard } from "./DraftSectionCard";

interface DraftOutlineEditorProps {
  actions: DraftClaimActions;
  /* The part on screen - see `draftParts`. */
  active: string;
  draft: EditableDocument;
  factContext: ClaimFactContext;
  facts: DocumentFacts | undefined;
  onRegenerateSection: (section: string) => void;
  onMoveClaim: (section: string, index: number, offset: -1 | 1) => void;
  requirements: ClaimRequirements;
}

/* The draft itself, one part on screen at a time: the opening lines and every section of
   the outline, all mounted so text typed into one survives a visit to another. Everything
   said *about* the draft - its fit, its saving, what blocks it - is the page's to place
   around this. */
export const DraftOutlineEditor = ({
  actions,
  active,
  draft,
  factContext,
  facts,
  onRegenerateSection,
  onMoveClaim,
  requirements,
}: DraftOutlineEditorProps) => (
  <>
    <DraftIdentityCard actions={actions} draft={draft} facts={facts} hidden={active !== IDENTITY_PART} />

    {draft.outline.sections.map((section, index) => (
      <DraftSectionCard
        actions={actions}
        draft={draft}
        factContext={factContext}
        facts={facts}
        headingId={`${sectionPartId(index)}-heading`}
        hidden={active !== sectionPartId(index)}
        key={section.name}
        onRegenerate={() => onRegenerateSection(section.name)}
        onMoveClaim={(claimIndex, offset) => onMoveClaim(section.name, claimIndex, offset)}
        requirements={requirements}
        section={section}
      />
    ))}
  </>
);
