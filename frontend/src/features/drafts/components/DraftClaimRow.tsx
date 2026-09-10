import { type ReactNode, useState } from "react";
import { Check, Pencil, RefreshCw, Trash2 } from "lucide-react";

import type { DraftClaim, DraftFact } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { StatusBadge } from "@/ui/StatusBadge";
import { Textarea } from "@/ui/Input";
import type { DraftClaimActions } from "../model/drafts.types";
import type { Removability } from "../model/draftClaims";
import { claimTypeExplanations, claimTypeLabels, claimTypeTones } from "../model/draftLabels";

interface DraftClaimRowProps {
  actions: DraftClaimActions;
  claim: DraftClaim;
  /* The confirmation flow for a `pending` line, supplied by the section. */
  factResolution?: ReactNode;
  /* The facts the accounting says stand behind this line, resolved by the list. */
  facts: DraftFact[];
  /* Which command removes this line, or why none does - decided once by the list. */
  removal: Removability;
}

/* Icons instead of spelled-out labels: on sixty stacked rows the labels were wider than
   the lines they acted on. */
const rowActionClasses = "min-h-9 px-2";

/* Fixed rather than shrink-to-fit, so every row's status lands in the same column; wide
   enough for the longest backend label, "מורכב מכמה עובדות". */
const marginClasses = "w-full shrink-0 pt-0.5 sm:w-36";

/* One line of the draft: status, text, backing facts, actions. Computes nothing about the
   draft itself - removability and linked facts are the list's answers. */
export const DraftClaimRow = ({ actions, claim, factResolution, facts, removal }: DraftClaimRowProps) => {
  const [text, setText] = useState(claim.text);
  /* The server's text wins on an underlying change (regeneration, rebuild, conflict
     resolution). Set during render, not an effect, so the row never paints a superseded
     line; an in-flight edit survives in the autosave buffer regardless. */
  const [syncedText, setSyncedText] = useState(claim.text);
  if (claim.text !== syncedText) {
    setSyncedText(claim.text);
    setText(claim.text);
  }

  const [editing, setEditing] = useState(false);

  /* The line as it stood when this edit began, so a revert hands back exactly what the
     backend still counts as canonical rather than a value guessed after the fact. */
  const [editOriginal, setEditOriginal] = useState<string | null>(null);
  const revertTarget = editing && editOriginal !== null && text !== editOriginal ? editOriginal : null;

  const evidenceLabel = facts.length === 1 ? "העובדה שמאחורי השורה" : `${facts.length} עובדות שמאחורי השורה`;

  return (
    <li className="flex flex-wrap items-start gap-x-3 gap-y-1.5 py-3 first:pt-0">
      <div className={marginClasses}>
        <StatusBadge tone={claimTypeTones[claim.claim_type]}>{claimTypeLabels[claim.claim_type]}</StatusBadge>
      </div>

      <div className="min-w-0 flex-1">
        {/* `text`, not `claim.text`: an edit still in the autosave buffer is what the user
            last typed. */}
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

        {/* Only once typed text actually diverges from the line this edit opened with -
            not on entering edit mode, and not before it has actually disconnected. */}
        {revertTarget === null ? null : (
          <Callout
            action={
              <Button
                onClick={() => {
                  setText(revertTarget);
                  actions.onEdit(claim, revertTarget);
                  actions.onCommit();
                }}
                size="compact"
                variant="secondary"
              >
                שחזור הטקסט הקודם
              </Button>
            }
            className="mt-2"
            role="alert"
            title="השורה מנותקת מהעובדה הקנונית"
            tone="warning"
          >
            <p dir="auto">
              העריכה משנה את הניסוח בלי לשנות את מה שעומד מאחורי השורה. שחזור הטקסט הקודם מחבר אותה מחדש.
            </p>
          </Callout>
        )}

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

        {claim.claim_type === "pending" ? (
          <>
            <Callout className="mt-2" title="הטקסט הזה חוסם אישור" tone="blocker">
              <p dir="auto">{claim.pending_reason ?? claimTypeExplanations.pending}</p>
            </Callout>
            {factResolution}
          </>
        ) : null}

        {removal.route === "none" && removal.reason !== undefined ? (
          <p className="mt-1.5 px-2 text-support leading-6 text-cv-text-muted">{removal.reason}</p>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        <Button
          aria-label={editing ? "סיום עריכת השורה" : "עריכת השורה"}
          className={rowActionClasses}
          onClick={() => {
            if (editing) {
              actions.onCommit();
              setEditOriginal(null);
            } else {
              setEditOriginal(text);
            }
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
