import { type ReactNode, useEffect, useState } from "react";
import { Database, RefreshCw, Trash2 } from "lucide-react";

import type { DraftClaim, DraftFact, WorkingDraft, WorkingDraftFacts } from "../../api/contracts";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
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

/* An action on one line of sixty. Spelled out, the two labels were wider than most of the
   lines they acted on and repeated themselves down the whole page; as icons they carry
   the same accessible name and stop competing with the text for width. */
const rowActionClasses = "min-h-9 px-2";

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
    /* A row, not a card. Every line of the draft used to be its own bordered, shadowed,
       lifting surface, so a document of sixty lines was sixty stacked boxes and the text
       inside them - the only thing on the screen the user came to read - was the least
       prominent part. The rows are separated by the list's own hairline instead. */
    <li className="group py-3 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <StatusBadge tone={claimTypeTones[claim.claim_type]}>{claimTypeLabels[claim.claim_type]}</StatusBadge>
        {/* Held out of the flow until the row is touched, so a page of rows is a page of
            text. Focus-within keeps them reachable by keyboard, where hover is not. */}
        <div className="flex gap-1 opacity-0 transition-opacity duration-150 focus-within:opacity-100 group-focus-within:opacity-100 group-hover:opacity-100">
          <Button
            aria-label="יצירה מחדש של השורה"
            className={rowActionClasses}
            disabled={unsaved}
            onClick={() => onRegenerate(claim)}
            title="יצירה מחדש של השורה"
            variant="ghost"
          >
            <RefreshCw aria-hidden="true" className="size-4" />
          </Button>
          {removal.route === "none" ? null : (
            <Button
              aria-label="הסרת השורה"
              className={rowActionClasses}
              onClick={() => onRemove(claim)}
              title="הסרת השורה"
              variant="ghost"
            >
              <Trash2 aria-hidden="true" className="size-4" />
            </Button>
          )}
        </div>
      </div>

      {/* The label is what names the control for a screen reader, and printed above every
          row it was a sixth repeated string down the page. It stays in the accessibility
          tree and leaves the layout. */}
      <TextArea
        aria-label="טקסט השורה"
        className="mt-2 min-h-16 resize-y border-transparent bg-transparent px-2 py-1.5 shadow-none hover:border-cv-border focus:border-cv-accent"
        dir="auto"
        onBlur={onBlur}
        onChange={(event) => {
          setText(event.target.value);
          onEdit(claim, event.target.value);
        }}
        value={text}
      />

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
          <Callout className="mt-2" title="הטקסט הזה חוסם אישור" tone="blocker">
            <p dir="auto">{claim.pending_reason ?? claimTypeExplanations.pending}</p>
          </Callout>
          {factResolution}
        </>
      ) : null}

      {/* The facts behind the line, as a note under it rather than a tinted box inside a
          box. The green mark on each fact is what says these are the confirmed backing;
          a full panel with its own heading said it a second time, once per row. */}
      {linked.length === 0 ? null : (
        <details className="mt-1.5 px-2">
          <summary className="inline-flex cursor-pointer items-center gap-1.5 text-support text-cv-text-muted">
            <Database aria-hidden="true" className="size-3.5 text-cv-success" />
            {linked.length === 1 ? "העובדה שמאחורי השורה" : `${linked.length} עובדות שמאחורי השורה`}
          </summary>
          <ul className="mt-1.5 flex flex-col gap-1.5">{linked.map(factRow)}</ul>
        </details>
      )}

      {/* Both lines describe the removal control, so they appear where it does: with the
          row under the pointer or the keyboard, not printed under all sixty rows at
          once. */}
      {removal.route === "none" && removal.reason !== undefined ? (
        <p className="mt-1.5 hidden px-2 text-support leading-6 text-cv-text-muted group-focus-within:block group-hover:block">
          {removal.reason}
        </p>
      ) : null}

      {removal.route === "selection" ? (
        <p className="mt-1.5 hidden px-2 text-support leading-6 text-cv-text-muted group-focus-within:block group-hover:block">
          הסרת השורה מחריגה את העובדה שמאחוריה ובונה את הטיוטה מחדש בלעדיה.
        </p>
      ) : null}
    </li>
  );
};
