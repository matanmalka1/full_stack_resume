import type { ReactNode } from "react";

import type { DocumentFacts, EditableDocument } from "../model/drafts.types";
import type { ClaimFactContext, DraftClaimActions } from "../model/drafts.types";
import { DraftIdentityCard } from "./DraftIdentityCard";
import { DraftSectionCard } from "./DraftSectionCard";
import { DraftSectionNav } from "./DraftSectionNav";

interface DraftOutlineEditorProps {
  actions: DraftClaimActions;
  draft: EditableDocument;
  factContext: ClaimFactContext;
  facts: DocumentFacts | undefined;
  /* The undo/redo controls, placed beside the heading of the text they act on. */
  history: ReactNode;
  onRegenerateSection: (section: string) => void;
  onMoveClaim: (section: string, index: number, offset: -1 | 1) => void;
}

const sectionHeadingId = (index: number): string => `draft-section-${index}`;

/* The draft itself, in reading order: a heading with the tools that act on the whole
   text, the opening lines, then every section of the outline the projection named.
   Everything said *about* the draft - how it was built, what blocks it, the errors - is
   the page's to place around this. */
export const DraftOutlineEditor = ({
  actions,
  draft,
  factContext,
  facts,
  history,
  onRegenerateSection,
  onMoveClaim,
}: DraftOutlineEditorProps) => (
  <section aria-labelledby="draft-outline-heading" className="flex flex-col gap-section-gap">
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-heading-sm font-bold text-cv-text" id="draft-outline-heading">
          תוכן קורות החיים
        </h2>
        {history}
      </div>
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
    </div>

    <DraftIdentityCard actions={actions} draft={draft} facts={facts} />

    {draft.outline.sections.map((section, index) => (
      <DraftSectionCard
        actions={actions}
        draft={draft}
        factContext={factContext}
        facts={facts}
        headingId={sectionHeadingId(index)}
        key={section.name}
        onRegenerate={() => onRegenerateSection(section.name)}
        onMoveClaim={(claimIndex, offset) => onMoveClaim(section.name, claimIndex, offset)}
        section={section}
      />
    ))}
  </section>
);
