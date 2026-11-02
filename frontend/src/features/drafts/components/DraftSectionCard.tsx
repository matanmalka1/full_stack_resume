import { Plus, RefreshCw } from "lucide-react";
import { useId, useState } from "react";

import type { DocumentFacts, EditableDocument } from "../model/drafts.types";
import { Button } from "@/ui/Button";
import { Textarea } from "@/ui/Input";
import { Tooltip } from "@/ui/Tooltip";
import { cardClasses } from "@/ui/surface";
import type { ClaimFactContext, DraftClaimActions } from "../model/drafts.types";
import type { ClaimRequirements } from "../model/draftFit";
import { ClaimFactResolution } from "./ClaimFactResolution";
import { DraftClaimList } from "./DraftClaimList";

/* DraftClaimList intentionally receives a render callback so this section can inject its
   own fact-resolution context for each claim. */
/* oxlint-disable react/no-unstable-nested-components */

type DraftOutlineSection = EditableDocument["outline"]["sections"][number];

interface DraftSectionCardProps {
  actions: DraftClaimActions;
  draft: EditableDocument;
  factContext: ClaimFactContext;
  facts: DocumentFacts | undefined;
  /* Its own id, so the heading names the card for assistive tech. */
  headingId: string;
  /* Another part is open. The card stays mounted so a line being edited in it keeps
     its text. */
  hidden: boolean;
  onRegenerate: () => void;
  onMoveClaim: (index: number, offset: -1 | 1) => void;
  requirements: ClaimRequirements;
  section: DraftOutlineSection;
}

/* The two commands a section header carries: a square, outlined 36px button each. On a
   wide screen adding a line is spelled out, as the design draws it; on a phone it is the
   plus alone, and the name stays for assistive tech. */
const headerButton =
  "inline-flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-control-sm border border-cv-border bg-cv-surface text-support font-bold text-cv-text transition-colors hover:bg-cv-surface-muted disabled:cursor-not-allowed disabled:opacity-50";

/* A.4 frame 3: one section of the draft outline - its heading, the commands that act on
   the whole section, and the claims in it. The only thing it adds to the list below it
   is the section context an unsupported line needs to become a fact.

   A card at every width, as the design draws it: the heading and its commands over the
   section's lines, each line divided from the next by a hairline that runs to the
   card's edge. */
export const DraftSectionCard = ({
  actions,
  draft,
  factContext,
  facts,
  headingId,
  hidden,
  onRegenerate,
  onMoveClaim,
  requirements,
  section,
}: DraftSectionCardProps) => {
  const [adding, setAdding] = useState(false);
  const [text, setText] = useState("");
  const textareaId = useId();

  const submit = () => {
    const trimmed = text.trim();
    if (trimmed === "") {
      return;
    }
    actions.onAdd(section.name, trimmed);
    setText("");
    setAdding(false);
  };

  return (
    <section aria-labelledby={headingId} className={cardClasses("overflow-hidden")} hidden={hidden}>
      <header className="flex items-start justify-between gap-2 px-5 py-4 max-lg:px-3.5 max-lg:pt-3.5 max-lg:pb-2.5">
        <div className="min-w-0">
          <h2
            className="truncate text-heading-card font-extrabold text-cv-text max-lg:text-body"
            dir="auto"
            id={headingId}
          >
            {section.name}
          </h2>
          <p className="text-support text-cv-text-muted max-lg:text-caption">
            {section.claims.length === 1 ? "שורה אחת" : `${section.claims.length} שורות`}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {/* No up/down controls for the section itself: section order is the Profile's,
              and validation refuses any other, so a moved section could never be approved. */}
          <Tooltip label="יצירה מחדש של הפרק">
            <button
              aria-label="יצירה מחדש של הפרק"
              className={`${headerButton} w-9`}
              disabled={actions.regenerationDisabled}
              onClick={onRegenerate}
              type="button"
            >
              <RefreshCw aria-hidden="true" className="size-icon-md" />
            </button>
          </Tooltip>
          <button
            aria-expanded={adding}
            className={`${headerButton} px-3 max-lg:w-9 max-lg:px-0`}
            onClick={() => setAdding(true)}
            type="button"
          >
            <Plus aria-hidden="true" className="size-icon-md" />
            <span className="max-lg:sr-only">שורה חדשה</span>
          </button>
        </div>
      </header>

      <DraftClaimList
        actions={actions}
        claims={section.claims}
        draft={draft}
        emptyLabel="אין כרגע שורות בסעיף הזה."
        factResolution={(claim) => (
          <ClaimFactResolution
            beforeResolve={factContext.beforeResolve}
            afterResolve={factContext.afterResolve}
            onResolvingChange={factContext.onResolvingChange}
            analysisId={factContext.analysisId}
            applicationId={factContext.applicationId}
            claim={claim}
            draft={draft}
            language={factContext.language}
            profile={factContext.profile}
            section={section.name}
          />
        )}
        facts={facts}
        onMove={onMoveClaim}
        requirements={requirements}
      />

      {adding ? (
        <div className="flex flex-col gap-2 border-t border-cv-hairline bg-cv-canvas px-5 py-4 max-lg:px-3.5">
          <label className="text-support font-medium text-cv-text" htmlFor={textareaId}>
            טקסט השורה החדשה
          </label>
          <Textarea
            className="min-h-16 resize-y"
            dir="auto"
            id={textareaId}
            onChange={(event) => setText(event.target.value)}
            value={text}
          />
          <p className="text-caption text-cv-text-muted">
            שורה חדשה נשמרת כפי שנכתבה ומסומנת כ"ללא ביסוס" עד שעובדה מאושרת תעמוד מאחוריה.
          </p>
          <div className="flex items-center gap-2">
            <Button disabled={actions.locked || text.trim() === ""} onClick={submit}>
              הוספת השורה
            </Button>
            <Button
              onClick={() => {
                setAdding(false);
                setText("");
              }}
              variant="secondary"
            >
              ביטול
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  );
};
