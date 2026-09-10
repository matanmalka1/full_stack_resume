import { Layers3, Plus, RefreshCw } from "lucide-react";
import { useId, useState } from "react";

import type { WorkingDraft, WorkingDraftFacts } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { Textarea } from "@/ui/Input";
import type { ClaimFactContext, DraftClaimActions } from "../model/drafts.types";
import { ClaimFactResolution } from "./ClaimFactResolution";
import { DraftClaimList } from "./DraftClaimList";

/* DraftClaimList intentionally receives a render callback so this section can inject its
   own fact-resolution context for each claim. */
/* oxlint-disable react/no-unstable-nested-components */

type DraftOutlineSection = WorkingDraft["outline"]["sections"][number];

interface DraftSectionCardProps {
  actions: DraftClaimActions;
  draft: WorkingDraft;
  factContext: ClaimFactContext;
  facts: WorkingDraftFacts | undefined;
  /* Its own id, so the section navigation above can reach it and so the heading names the
     card for assistive tech. */
  headingId: string;
  onRegenerate: () => void;
  section: DraftOutlineSection;
}

/* A.4 frame 3: one section of the draft outline - its heading, its regenerate action, and
   the claims in it. The only thing it adds to the list below it is the section context an
   unsupported line needs to become a fact. */
export const DraftSectionCard = ({
  actions,
  draft,
  factContext,
  facts,
  headingId,
  onRegenerate,
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
    <Card
      aria-labelledby={headingId}
      className="flex scroll-mt-24 flex-col gap-2 bg-cv-surface p-4 shadow-surface sm:p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-cv-border pb-3">
        <div className="flex min-w-0 items-center gap-2">
          <Layers3 aria-hidden="true" className="size-4 shrink-0 text-cv-accent" />
          <h3 className="truncate text-heading-sm font-bold text-cv-text" dir="auto" id={headingId}>
            {section.name}
          </h3>
          <span className="shrink-0 text-support text-cv-text-muted">
            {section.claims.length === 1 ? "שורה אחת" : `${section.claims.length} שורות`}
          </span>
        </div>
        <Button disabled={actions.regenerationDisabled} onClick={onRegenerate} variant="secondary">
          <RefreshCw aria-hidden="true" className="size-4" />
          יצירה מחדש של הפרק
        </Button>
      </div>

      <DraftClaimList
        actions={actions}
        claims={section.claims}
        draft={draft}
        emptyLabel="אין כרגע שורות בסעיף הזה."
        factResolution={(claim) => (
          <ClaimFactResolution
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
      />

      {adding ? (
        <div className="flex flex-col gap-2 border-t border-cv-border pt-3">
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
          <div className="flex items-center gap-2">
            <Button disabled={text.trim() === ""} onClick={submit}>
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
        <div className="border-t border-cv-border pt-3">
          <Button onClick={() => setAdding(true)} variant="secondary">
            <Plus aria-hidden="true" className="size-4" />
            הוספת שורה לפרק
          </Button>
        </div>
      )}
    </Card>
  );
};
