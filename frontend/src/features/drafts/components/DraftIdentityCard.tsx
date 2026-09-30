import type { DocumentFacts, EditableDocument } from "../model/drafts.types";
import type { DraftClaimActions } from "../model/drafts.types";
import { DraftClaimList } from "./DraftClaimList";

interface DraftIdentityCardProps {
  actions: DraftClaimActions;
  draft: EditableDocument;
  facts: DocumentFacts | undefined;
}

/* The document's opening lines: the headline and the contact details. They come from the
   candidate's profile rather than from the selection plan, which is why they are their
   own part above the sections and why neither of them can be removed here. Drawn like the
   sections below it, so the editor reads top to bottom as the CV does. */
export const DraftIdentityCard = ({ actions, draft, facts }: DraftIdentityCardProps) => (
  <section aria-labelledby="draft-structure-heading" className="flex flex-col gap-3">
    <header className="flex flex-col gap-0.5 border-b border-cv-border-strong pb-2">
      <h3 className="text-heading-sm font-bold text-cv-text" id="draft-structure-heading">
        כותרת ופרטי קשר
      </h3>
      {/* Said once for every contact line, rather than repeated under each of them. */}
      <p className="text-caption leading-5 text-cv-text-muted">
        נבנים מהפרופיל ולא מהעובדות שנבחרו לטיוטה, ולכן חוזרים בכל בנייה מחדש ואי אפשר להסיר אותם כאן.
      </p>
    </header>

    <DraftClaimList
      actions={actions}
      claims={[draft.outline.headline, ...draft.outline.contacts]}
      draft={draft}
      emptyLabel="אין כרגע כותרת ופרטי קשר בטיוטה."
      facts={facts}
    />
  </section>
);
