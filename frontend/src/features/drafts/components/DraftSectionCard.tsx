import { Plus, RefreshCw } from "lucide-react";
import { useId, useState } from "react";

import type { DocumentFacts, EditableDocument } from "../model/drafts.types";
import { Button } from "@/ui/Button";
import { Textarea } from "@/ui/Input";
import type { ClaimFactContext, DraftClaimActions } from "../model/drafts.types";
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
  /* Its own id, so the section navigation above can reach it and so the heading names the
     card for assistive tech. */
  headingId: string;
  onRegenerate: () => void;
  onMoveClaim: (index: number, offset: -1 | 1) => void;
  section: DraftOutlineSection;
}

/* A.4 frame 3: one section of the draft outline - its heading, its regenerate action, and
   the claims in it. The only thing it adds to the list below it is the section context an
   unsupported line needs to become a fact.

   Drawn as the document's own section - a heading over a rule - rather than as a card:
   every section was a framed, shadowed box, so the editor read as a stack of panels
   instead of as the CV it is editing. */
export const DraftSectionCard = ({
  actions,
  draft,
  factContext,
  facts,
  headingId,
  onRegenerate,
  onMoveClaim,
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
    <section aria-labelledby={headingId} className="flex scroll-mt-24 flex-col gap-3">
      <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-cv-border-strong pb-2">
        <div className="flex min-w-0 items-baseline gap-2">
          <h3 className="truncate text-heading-sm font-bold text-cv-text" dir="auto" id={headingId}>
            {section.name}
          </h3>
          <span className="shrink-0 text-support text-cv-text-muted">
            {section.claims.length === 1 ? "שורה אחת" : `${section.claims.length} שורות`}
          </span>
        </div>
        {/* No up/down controls for the section itself: section order is the Profile's,
            and validation refuses any other, so a moved section could never be approved. */}
        <Button disabled={actions.regenerationDisabled} onClick={onRegenerate} variant="ghost">
          <RefreshCw aria-hidden="true" className="size-icon-md" />
          יצירה מחדש של הפרק
        </Button>
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
      />

      {adding ? (
        <div className="flex flex-col gap-2 rounded-control bg-cv-surface-muted p-3">
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
      ) : (
        <Button className="self-start" onClick={() => setAdding(true)} variant="ghost">
          <Plus aria-hidden="true" className="size-icon-md" />
          הוספת שורה לפרק
        </Button>
      )}
    </section>
  );
};
