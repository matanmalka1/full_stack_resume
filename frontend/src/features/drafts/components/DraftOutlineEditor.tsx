import type { WorkingDraft, WorkingDraftFacts } from "@/api/contracts";
import type { ClaimFactContext, DraftClaimActions } from "../drafts.types";
import { DraftIdentityCard } from "./DraftIdentityCard";
import { DraftSectionCard } from "./DraftSectionCard";
import { DraftSectionNav } from "./DraftSectionNav";

interface DraftOutlineEditorProps {
  actions: DraftClaimActions;
  draft: WorkingDraft;
  factContext: ClaimFactContext;
  facts: WorkingDraftFacts | undefined;
  onRegenerateSection: (section: string) => void;
}

const sectionHeadingId = (index: number): string => `draft-section-${index}`;

/* The draft itself, in reading order: the opening lines, then every section of the
   outline the projection named. Everything said *about* the draft - the fact accounting,
   the AI notices, the errors - is the page's to place around this. */
export const DraftOutlineEditor = ({
  actions,
  draft,
  factContext,
  facts,
  onRegenerateSection,
}: DraftOutlineEditorProps) => (
  <>
    <DraftIdentityCard actions={actions} draft={draft} facts={facts} />

    {/* One section needs no way to jump between sections. */}
    {draft.outline.sections.length > 1 ? (
      <DraftSectionNav
        sections={draft.outline.sections.map((section, index) => ({
          claims: section.claims.length,
          id: sectionHeadingId(index),
          name: section.name,
        }))}
      />
    ) : null}

    {draft.outline.sections.map((section, index) => (
      <DraftSectionCard
        actions={actions}
        draft={draft}
        factContext={factContext}
        facts={facts}
        headingId={sectionHeadingId(index)}
        key={section.name}
        onRegenerate={() => onRegenerateSection(section.name)}
        section={section}
      />
    ))}
  </>
);
