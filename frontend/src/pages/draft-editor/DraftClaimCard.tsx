import { type ReactNode, useEffect, useState } from "react";
import { Database, RefreshCw, Trash2 } from "lucide-react";

import type { DraftClaim, DraftFact, WorkingDraft, WorkingDraftFacts } from "../../api/contracts";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Field } from "../../ui/Field";
import { StatusBadge } from "../../ui/StatusBadge";
import { TextArea } from "../../ui/TextInput";
import { removability } from "./claimRemoval";
import { claimTypeExplanations, claimTypeLabels, claimTypeTones } from "./draftLabels";

interface DraftClaimCardProps {
  claim: DraftClaim;
  draft: WorkingDraft;
  facts: WorkingDraftFacts | undefined;
  onBlur: () => void;
  onEdit: (claim: DraftClaim, text: string) => void;
  onRegenerate: (claim: DraftClaim) => void;
  onRemove: (claim: DraftClaim) => void;
  factResolution?: ReactNode;
  /* True while an unsaved edit is in the autosave buffer. A regeneration freezes the
     saved version, so offering one now would regenerate away from what the user is
     looking at. */
  unsaved: boolean;
}

const factRow = (fact: DraftFact) => (
  <li className="flex gap-2 text-support leading-6 text-cv-text-muted" key={fact.fact_id}>
    <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-pill bg-cv-success" />
    <span dir="auto">{fact.text ?? "לא ניתן לקרוא את העובדה הזו מהידע."}</span>
  </li>
);

/* A.4 frame 3: the claim, its status in words, the facts behind it, and what may be done
   to it. The status is the backend's `claim_type`, not a judgement made here, and the
   supporting facts are named by their text - a user never has to read a fact ID. */
export const DraftClaimCard = ({
  claim,
  draft,
  facts,
  factResolution,
  onBlur,
  onEdit,
  onRegenerate,
  onRemove,
  unsaved,
}: DraftClaimCardProps) => {
  const linked = (facts?.facts ?? []).filter((fact) => claim.fact_ids.includes(fact.fact_id));
  const removal = removability(claim, draft, facts);
  const [text, setText] = useState(claim.text);

  /* The server's text wins whenever it changes underneath: a regeneration, a rebuilt
     selection, or the version the user kept after a conflict. Local typing is not lost by
     this - an unsaved edit is held in the autosave buffer, not here. */
  useEffect(() => {
    setText(claim.text);
  }, [claim.text]);

  return (
    <li className="group rounded-surface border border-cv-border bg-cv-surface p-4 shadow-surface transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:border-cv-accent/30 hover:shadow-floating sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <StatusBadge tone={claimTypeTones[claim.claim_type]}>
          {claimTypeLabels[claim.claim_type]}
        </StatusBadge>
        <div className="flex flex-wrap gap-2">
          <Button disabled={unsaved} onClick={() => onRegenerate(claim)} variant="secondary">
            <RefreshCw aria-hidden="true" className="size-4" />
            יצירה מחדש של השורה
          </Button>
          {removal.route === "none" ? null : (
            <Button onClick={() => onRemove(claim)} variant="secondary">
              <Trash2 aria-hidden="true" className="size-4" />
              הסרת השורה
            </Button>
          )}
        </div>
      </div>

      <Field className="mt-3" label="טקסט השורה">
        {(control) => (
          <TextArea
            {...control}
            className="min-h-24 resize-y bg-cv-surface-raised"
            dir="auto"
            onBlur={onBlur}
            onChange={(event) => {
              setText(event.target.value);
              onEdit(claim, event.target.value);
            }}
            value={text}
          />
        )}
      </Field>

      {/* The badge above already names the claim type in a word, and the facts panel
          below shows what backs it. Printed under all sixty-odd cards, this sentence
          restated both once per claim - five fixed strings repeated down a page tall
          enough that nothing on it was findable.

          It stays where it is not already answered: `pending` has no facts panel, because
          there are no facts, so its card would otherwise say nothing about why. The
          blocker callout is that explanation, and it carries the backend's own reason
          rather than the generic sentence - which is why the generic one is gone even
          here, and why the callout no longer waits for `pending_reason` to be present
          before saying that approval is blocked. */}
      {claim.claim_type === "pending" ? (
        <>
          <Callout className="mt-3" title="הטקסט הזה חוסם אישור" tone="blocker">
            <p dir="auto">{claim.pending_reason ?? claimTypeExplanations.pending}</p>
          </Callout>
          {factResolution}
        </>
      ) : null}

      {linked.length === 0 ? null : (
        <div className="mt-4 rounded-control border border-cv-success/20 bg-cv-success-soft p-3">
          <p className="flex items-center gap-2 text-support font-semibold text-cv-success">
            <Database aria-hidden="true" className="size-4" />
            העובדות שמאחורי השורה
          </p>
          <ul className="mt-2 flex flex-col gap-1.5">{linked.map(factRow)}</ul>
        </div>
      )}

      {removal.route === "none" && removal.reason !== undefined ? (
        <p className="mt-3 text-support leading-6 text-cv-text-muted">{removal.reason}</p>
      ) : null}

      {removal.route === "selection" ? (
        <p className="mt-3 text-support leading-6 text-cv-text-muted">
          הסרת השורה מחריגה את העובדה שמאחוריה ובונה את הטיוטה מחדש בלעדיה.
        </p>
      ) : null}
    </li>
  );
};
