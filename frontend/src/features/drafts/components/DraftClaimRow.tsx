import { type ReactNode, useState } from "react";
import { Check, Pencil, RefreshCw, Trash2 } from "lucide-react";

import type { DraftClaim, DraftFact } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { StatusBadge } from "@/ui/StatusBadge";
import { Textarea } from "@/ui/Input";
import type { DraftClaimActions } from "../drafts.types";
import type { Removability } from "../model/draftClaims";
import { claimTypeExplanations, claimTypeLabels, claimTypeTones } from "../model/draftLabels";

interface DraftClaimRowProps {
  actions: DraftClaimActions;
  claim: DraftClaim;
  /* Rendered under a `pending` line: the flow that turns unsupported text into a
     confirmed fact. Supplied by the section, which knows the Application context it
     needs. */
  factResolution?: ReactNode;
  /* The facts the accounting says stand behind this line, resolved by the list. */
  facts: DraftFact[];
  /* Which command removes this line, or why none does. Decided once per claim by the
     list rather than re-derived inside every row's markup. */
  removal: Removability;
}

/* An action on one line of sixty. Spelled out, the labels were wider than most of the
   lines they acted on and repeated themselves down the whole page; as icons they carry
   the same accessible name and stop competing with the text for width. */
const rowActionClasses = "min-h-9 px-2";

/* The margin column is a fixed width rather than shrink-to-fit, because each row is its
   own grid and an auto width would set the text column to a different place on every
   line. A fixed margin is what makes the statuses read as one column and the text as
   another. It is wide enough for the longest label the backend can send - "מורכב מכמה
   עובדות" - so a status wraps inside its own badge rather than pushing the text column
   somewhere else. Below `sm` it is the full row and the line follows underneath, which
   the row's own wrapping does; a second copy of the badge for narrow screens would be
   announced twice on every line. */
const marginClasses = "w-full shrink-0 pt-0.5 sm:w-36";

/* A.4 frame 3: one line of the draft - the claim, its status in words, the facts behind
   it, and what may be done to it.

   The status leads: a fixed margin at the row's start, so a page of sixty lines shows one
   straight column of statuses that can be scanned without reading a word, and the text
   always begins at the same place beside it. The controls keep the far edge - a thing
   said about the line and a thing done to it are not the same kind of thing and do not
   share a corner.

   The facts are marked lines rather than a bracketed block: each fact carries its own
   small mark in the tone of a verified thing, so backing is counted per fact rather than
   implied by one rule around all of them. Editing rings the text column instead of
   changing the field's own chrome, because what changed is the line, not the widget.

   It computes nothing about the draft. Removability and the linked facts are the list's
   answers, so one policy is applied per claim in one place. */
export const DraftClaimRow = ({ actions, claim, factResolution, facts, removal }: DraftClaimRowProps) => {
  const [text, setText] = useState(claim.text);
  /* The server's text wins whenever it changes underneath: a regeneration, a rebuilt
     selection, or the version the user kept after a conflict. Adjusted during render
     rather than in an effect - the row must never paint the superseded line first, and an
     unsaved edit is not lost by this, because it is held in the autosave buffer. */
  const [syncedText, setSyncedText] = useState(claim.text);
  if (claim.text !== syncedText) {
    setSyncedText(claim.text);
    setText(claim.text);
  }

  /* Per row, because that is the size of the decision. The screen is for reading a
     document and signing it; changing one line does not need the whole page to turn into
     a form, and the pencil is on every row so it is never somewhere else. */
  const [editing, setEditing] = useState(false);

  const evidenceLabel = facts.length === 1 ? "העובדה שמאחורי השורה" : `${facts.length} עובדות שמאחורי השורה`;

  return (
    /* A row, not a card. Every line of the draft used to be its own bordered, shadowed,
       lifting surface, so a document of sixty lines was sixty stacked boxes and the text
       inside them - the only thing on the screen the user came to read - was the least
       prominent part. The rows are separated by the list's own hairline instead. */
    <li className="flex flex-wrap items-start gap-x-3 gap-y-1.5 py-3 first:pt-0">
      {/* The status, in the margin, drawn once. It is the backend's `claim_type`, not a
          judgement made here. */}
      <div className={marginClasses}>
        <StatusBadge tone={claimTypeTones[claim.claim_type]}>{claimTypeLabels[claim.claim_type]}</StatusBadge>
      </div>

      <div className="min-w-0 flex-1">
        {/* `text` rather than `claim.text` in both branches: an edit still sitting in the
            autosave buffer is what the user last typed, and a row that reverted to the
            server's copy would show a line the user did not write and is about to approve
            something else.

            An open row is marked by the surface under it rather than by a ring, and the
            field keeps the focus ring every control in this application draws, so a
            keyboard user tabbing through the rows can see where they are. */}
        <div className={editing ? "rounded-control bg-cv-surface-muted" : undefined}>
          {editing ? (
            <Textarea
              aria-label="טקסט השורה"
              className="min-h-16 resize-y border-transparent bg-transparent px-2 py-1.5 shadow-none"
              dir="auto"
              onBlur={actions.onCommit}
              onChange={(event) => {
                setText(event.target.value);
                actions.onEdit(claim, event.target.value);
              }}
              value={text}
            />
          ) : (
            <p className="px-2 py-1.5 leading-7 text-cv-text" dir="auto">
              {text}
            </p>
          )}
        </div>

        {/* The facts behind the line, marked one by one. Approval is a signature on every
            line, so the evidence is not something the reader should go looking for one row
            at a time - but neither is it a second heading per row. Each mark says: this
            sentence is backed by this. The sentence naming the set stays in the
            accessibility tree. */}
        {facts.length === 0 ? null : (
          <ul aria-label={evidenceLabel} className="mt-1 flex flex-col gap-1 px-2">
            {facts.map((fact) => (
              <li className="flex items-start gap-2" dir="auto" key={fact.fact_id}>
                <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-pill bg-cv-success" />
                <span className="text-support leading-6 text-cv-text-muted">
                  {fact.text ?? "לא ניתן לקרוא את העובדה הזו מהידע."}
                </span>
              </li>
            ))}
          </ul>
        )}

        {/* The badge in the margin already names the claim type in a word, and the marks
            under the line show what backs it. `pending` has neither backing nor anything
            to show, so its blocker carries the backend's own reason for why approval is
            shut. */}
        {claim.claim_type === "pending" ? (
          <>
            <Callout className="mt-2" title="הטקסט הזה חוסם אישור" tone="blocker">
              <p dir="auto">{claim.pending_reason ?? claimTypeExplanations.pending}</p>
            </Callout>
            {factResolution}
          </>
        ) : null}

        {/* What removal would do rides on the removal button itself. A line that cannot be
            removed has no button to carry its reason, so that one stays where the reader
            can see it. */}
        {removal.route === "none" && removal.reason !== undefined ? (
          <p className="mt-1.5 px-2 text-support leading-6 text-cv-text-muted">{removal.reason}</p>
        ) : null}
      </div>

      {/* What may be done to the line, at the row's far edge and nothing else with it. All
          three controls are always drawn: a control that appears only under the pointer is
          one the reader has to already know is there, and on a touch screen there is no
          pointer to reveal it with. */}
      <div className="flex shrink-0 items-center gap-1">
        <Button
          aria-label={editing ? "סיום עריכת השורה" : "עריכת השורה"}
          className={rowActionClasses}
          onClick={() => {
            /* Closing the field settles what is buffered, the way a blur does, so the line
               the reader returns to is the line they typed. */
            if (editing) actions.onCommit();
            setEditing(!editing);
          }}
          title={editing ? "סיום עריכת השורה" : "עריכת השורה"}
          variant="ghost"
        >
          {editing ? (
            <Check aria-hidden="true" className="size-4 text-cv-accent" />
          ) : (
            <Pencil aria-hidden="true" className="size-4 text-cv-text-muted" />
          )}
        </Button>
        <Button
          aria-label="יצירה מחדש של השורה"
          className={rowActionClasses}
          disabled={actions.regenerationDisabled}
          onClick={() => actions.onRegenerate(claim)}
          title="יצירה מחדש של השורה"
          variant="ghost"
        >
          <RefreshCw aria-hidden="true" className="size-4 text-cv-text-muted" />
        </Button>
        {removal.route === "none" ? null : (
          <Button
            aria-label="הסרת השורה"
            className={rowActionClasses}
            onClick={() => actions.onRemove(claim)}
            title={
              removal.route === "selection"
                ? "הסרת השורה מחריגה את העובדה שמאחוריה ובונה את הטיוטה מחדש בלעדיה."
                : "הסרת השורה"
            }
            variant="ghost"
          >
            <Trash2 aria-hidden="true" className="size-4 text-cv-text-muted" />
          </Button>
        )}
      </div>
    </li>
  );
};
