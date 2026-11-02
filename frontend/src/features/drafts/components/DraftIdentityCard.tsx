import type { DocumentFacts, EditableDocument } from "../model/drafts.types";
import type { DraftClaimActions } from "../model/drafts.types";
import { cardClasses } from "@/ui/surface";
import { DraftClaimList } from "./DraftClaimList";

interface DraftIdentityCardProps {
  actions: DraftClaimActions;
  draft: EditableDocument;
  facts: DocumentFacts | undefined;
  /* Another part is open; see `DraftSectionCard`. */
  hidden: boolean;
}

/* The document's opening lines: the headline and the contact details. They come from the
   candidate's profile rather than from the selection plan, which is why they are their
   own part beside the sections and why neither of them can be removed here. Drawn as the
   section cards are. */
export const DraftIdentityCard = ({ actions, draft, facts, hidden }: DraftIdentityCardProps) => (
  <section aria-labelledby="draft-structure-heading" className={cardClasses("overflow-hidden")} hidden={hidden}>
    <header className="px-5 py-4 max-lg:px-3.5 max-lg:pt-3.5 max-lg:pb-2.5">
      <h2 className="text-heading-card font-extrabold text-cv-text max-lg:text-body" id="draft-structure-heading">
        כותרת ופרטי קשר
      </h2>
      {/* Said once for every contact line, rather than repeated under each of them. */}
      <p className="text-support text-cv-text-muted max-lg:text-caption">
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
