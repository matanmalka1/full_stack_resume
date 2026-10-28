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
   sections below it, so the editor reads top to bottom as the CV does - a card at every
   width, as they are. */
export const DraftIdentityCard = ({ actions, draft, facts }: DraftIdentityCardProps) => (
  <section
    aria-labelledby="draft-structure-heading"
    className="flex flex-col gap-3 max-lg:rounded-surface max-lg:border max-lg:border-cv-border max-lg:bg-cv-surface max-lg:p-card-padding lg:overflow-hidden lg:rounded-surface lg:border lg:border-cv-hairline lg:bg-cv-surface lg:px-5 lg:pt-4 lg:pb-3 lg:shadow-card"
  >
    <header className="flex flex-col gap-0.5 border-b border-cv-border-strong pb-2 max-lg:border-cv-border lg:-mx-5 lg:border-cv-hairline lg:px-5 lg:pb-3">
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
