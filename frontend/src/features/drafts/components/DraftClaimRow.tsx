import { type ReactNode, useState } from "react";
import { ArrowDown, ArrowUp, Check, type LucideIcon, Pencil, RefreshCw, Trash2 } from "lucide-react";

import type { DraftClaim, DraftFact } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Dialog } from "@/ui/Dialog";
import { Disclosure, DisclosureSummary } from "@/ui/Disclosure";
import { StatusBadge } from "@/ui/StatusBadge";
import { Textarea } from "@/ui/Input";
import { Tooltip } from "@/ui/Tooltip";
import { cx } from "@/ui/cx";
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
  move?: { canMoveDown: boolean; canMoveUp: boolean; onMove: (offset: -1 | 1) => void };
}

/* An icon button with its name in a tooltip: on sixty stacked rows spelled-out labels
   were wider than the lines they acted on. */
const RowAction = ({
  className,
  disabled,
  icon: Icon,
  label,
  onClick,
}: {
  className?: string;
  disabled?: boolean;
  icon: LucideIcon;
  label: string;
  onClick: () => void;
}) => (
  <Tooltip label={label}>
    <Button aria-label={label} className="min-h-8 px-1.5" disabled={disabled} onClick={onClick} variant="ghost">
      <Icon aria-hidden="true" className={cx("size-icon-md", className ?? "text-cv-text-muted")} />
    </Button>
  </Tooltip>
);

/* Where the line came from, folded under the line: the fact behind it, how its wording
   relates to that fact, and - for reworded lines - the evidence the review accepted.

   This is the content swap the draft performed, made readable per line. It used to be a
   list of bullets printed under every row whether or not anyone asked, which on a
   sixty-line CV doubled the page; folded, each row keeps one quiet line that opens onto
   the whole story. */
const ClaimSource = ({
  claim,
  facts,
  removalReason,
}: {
  claim: DraftClaim;
  facts: DraftFact[];
  removalReason?: string;
}) => {
  const [open, setOpen] = useState(false);
  const reviewAssertions = new Map(
    claim.review_evidence?.assertions.map(
      (assertion) =>
        [JSON.stringify([assertion.claim_quote, assertion.fact_ids, assertion.source_quotes]), assertion] as const,
    ) ?? [],
  );
  const summary =
    facts.length === 0 ? "פרטי השורה" : facts.length === 1 ? "המקור: עובדה אחת" : `המקור: ${facts.length} עובדות`;

  return (
    <details className="text-support" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <DisclosureSummary className="w-fit font-medium text-cv-text-muted hover:text-cv-text" open={open}>
        {summary}
      </DisclosureSummary>
      <div className="mt-2 flex flex-col gap-2 border-s-2 border-cv-border ps-3 leading-6">
        {/* A pending line's callout already says this, right above. */}
        {claim.claim_type === "pending" ? null : (
          <p className="text-cv-text-muted">{claimTypeExplanations[claim.claim_type]}</p>
        )}

        {facts.length === 0 ? null : (
          <ul
            aria-label={facts.length === 1 ? "העובדה שמאחורי השורה" : "העובדות שמאחורי השורה"}
            className="flex flex-col gap-1.5"
          >
            {facts.map((fact) => (
              <li className="rounded-control bg-cv-surface-muted px-2.5 py-1.5" key={fact.fact_id}>
                <p className="text-caption font-semibold text-cv-text-muted">העובדה במאגר</p>
                {/* A fact identical to the line adds nothing beside it; saying so is the
                    information. The text is not repeated. */}
                {fact.text === claim.text ? (
                  <p className="text-cv-text-muted">הנוסח בקורות החיים זהה לנוסח העובדה.</p>
                ) : (
                  <p className="text-cv-text" dir="auto">
                    {fact.text ?? "לא ניתן לקרוא את העובדה הזו מהמאגר."}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}

        {claim.claim_type === "reviewed" && claim.review_evidence != null ? (
          <div className="flex flex-col gap-1.5">
            <p className="font-semibold text-cv-text">למה הניסוח אושר?</p>
            <p className="text-cv-text-muted">
              הניסוח נבדק סמנטית מול העובדות המקושרות. זו בדיקת תמיכה של המודל, לא הוכחה דטרמיניסטית.
            </p>
            <ul className="flex flex-col gap-1.5">
              {Array.from(reviewAssertions, ([key, assertion]) => (
                <li className="rounded-control bg-cv-surface-muted px-2.5 py-1.5" key={key}>
                  <p dir="auto">טענה: {assertion.claim_quote}</p>
                  {Array.from(new Set(assertion.source_quotes), (quote) => (
                    <p className="mt-1 text-cv-text-muted" dir="auto" key={quote}>
                      מקור: {quote}
                    </p>
                  ))}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {removalReason === undefined ? null : <p className="text-cv-text-muted">{removalReason}</p>}
      </div>
    </details>
  );
};

/* One line of the draft: its text, where it came from, and what can be done to it.
   Computes nothing about the draft itself - removability and linked facts are the list's
   answers. */
export const DraftClaimRow = ({ actions, claim, factResolution, facts, move, removal }: DraftClaimRowProps) => {
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

  /* A single misclick on a dense list of rows must not be able to discard a line or
     exclude the fact behind it - the confirmation is the only gate before either takes
     effect. */
  const [confirmingRemoval, setConfirmingRemoval] = useState(false);

  /* The line as it stood when this edit began, so a revert hands back exactly what the
     backend still counts as canonical rather than a value guessed after the fact. */
  const [editOriginal, setEditOriginal] = useState<string | null>(null);
  const revertTarget = editing && editOriginal !== null && text !== editOriginal ? editOriginal : null;

  const editingReviewedClaim = claim.claim_type === "reviewed";
  const pending = claim.claim_type === "pending";
  /* A line linked to facts can be checked as written. The headline and the contacts are
     not factual claims, and an unlinked line has nothing to be checked against - it is
     resolved below, as a fact. */
  const reviewable = claim.fact_ids.length > 0 && claim.style !== "headline" && claim.style !== "contact";

  const toggleEditing = () => {
    if (editing) {
      actions.onCommit();
      setEditOriginal(null);
    } else {
      setEditOriginal(text);
    }
    setEditing(!editing);
  };

  return (
    <li
      className={cx(
        "flex scroll-mt-24 flex-col gap-2 py-3 first:pt-0 focus-visible:outline-offset-4",
        pending && "border-s-2 border-s-cv-blocker ps-3",
      )}
      id={`draft-claim-${claim.claim_id}`}
      tabIndex={-1}
    >
      {/* `text`, not `claim.text`: an edit still in the autosave buffer is what the user
          last typed. The text takes the row's whole width; everything about it sits on
          the line below. */}
      {editing ? (
        <Textarea
          aria-label="טקסט השורה"
          className="min-h-16 resize-y"
          dir="auto"
          onBlur={actions.onCommit}
          onChange={(event) => {
            setText(event.target.value);
            actions.onEdit(claim, event.target.value);
          }}
          readOnly={actions.locked}
          value={text}
        />
      ) : (
        <p className="text-body leading-7 text-cv-text" dir="auto">
          {text}
        </p>
      )}

      {/* Only once typed text actually diverges from the line this edit opened with -
          not on entering edit mode, and not before it has actually disconnected. */}
      {revertTarget === null ? null : (
        <Callout
          action={
            <Button
              disabled={actions.locked}
              onClick={() => {
                setText(revertTarget);
                actions.onEdit(claim, revertTarget);
                actions.onCommit();
              }}
              variant="secondary"
            >
              {editingReviewedClaim ? "שחזור הנוסח שנבדק" : "שחזור הטקסט הקודם"}
            </Button>
          }
          role="alert"
          title={editingReviewedClaim ? "העריכה מבטלת את הביקורת הקודמת" : "השורה מנותקת מהעובדה הקנונית"}
          tone="warning"
        >
          <p dir="auto">
            {editingReviewedClaim
              ? "הבדיקה חלה על הנוסח הקודם בלבד. לאחר השמירה השורה תחזור למצב שממתין לאימות."
              : "העריכה משנה את הניסוח בלי לשנות את מה שעומד מאחורי השורה. שחזור הטקסט הקודם מחבר אותה מחדש."}
          </p>
        </Callout>
      )}

      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
        <StatusBadge className="px-2 py-0.5" tone={claimTypeTones[claim.claim_type]}>
          {claimTypeLabels[claim.claim_type]}
        </StatusBadge>

        <div className="flex items-center gap-0.5">
          {move === undefined ? null : (
            <>
              <RowAction
                disabled={actions.locked || !move.canMoveUp}
                icon={ArrowUp}
                label="הזזת השורה למעלה"
                onClick={() => move.onMove(-1)}
              />
              <RowAction
                disabled={actions.locked || !move.canMoveDown}
                icon={ArrowDown}
                label="הזזת השורה למטה"
                onClick={() => move.onMove(1)}
              />
            </>
          )}
          <RowAction
            className={editing ? "text-cv-accent" : undefined}
            disabled={actions.locked && !editing}
            icon={editing ? Check : Pencil}
            label={editing ? "סיום עריכת השורה" : "עריכת השורה"}
            onClick={toggleEditing}
          />
          <RowAction
            disabled={actions.regenerationDisabled}
            icon={RefreshCw}
            label="יצירה מחדש של השורה"
            onClick={() => actions.onRegenerate(claim)}
          />
          {removal.route === "none" ? null : (
            <RowAction
              disabled={actions.locked}
              icon={Trash2}
              label="הסרת השורה"
              onClick={() => setConfirmingRemoval(true)}
            />
          )}
        </div>
      </div>

      {pending ? (
        <>
          <Callout
            action={
              reviewable ? (
                <Button
                  disabled={actions.regenerationDisabled}
                  onClick={() => actions.onReview(claim)}
                  variant="secondary"
                >
                  בדיקת הניסוח מול העובדות
                </Button>
              ) : undefined
            }
            title="הטקסט הזה חוסם אישור"
            tone="blocker"
          >
            <p>{claimTypeExplanations.pending}</p>
            {reviewable ? (
              <p className="mt-1">אם המשמעות זהה לעובדות שמאחוריה, הבדיקה תאשר את השורה בלי לשנות אותה.</p>
            ) : null}
            {/* The validator's own reason is English and technical - evidence for a bug
                report, not the explanation - so it is folded rather than shown. */}
            {claim.pending_reason == null ? null : (
              <Disclosure summary="פרטי הסיבה">
                <p dir="auto">{claim.pending_reason}</p>
              </Disclosure>
            )}
          </Callout>
          {factResolution}
        </>
      ) : null}

      {/* A pending line with nothing behind it has no source to open; its callout above
          is the whole story. */}
      {pending && facts.length === 0 ? null : (
        <ClaimSource
          claim={claim}
          facts={facts}
          removalReason={removal.route === "none" ? removal.reason : undefined}
        />
      )}

      {removal.route === "none" ? null : (
        <Dialog
          footer={
            <>
              <Button onClick={() => setConfirmingRemoval(false)} variant="secondary">
                ביטול
              </Button>
              <Button
                onClick={() => {
                  actions.onRemove(claim);
                  setConfirmingRemoval(false);
                }}
                variant="destructive"
              >
                אישור ההסרה
              </Button>
            </>
          }
          headingId={`remove-claim-heading-${claim.claim_id}`}
          onClose={() => setConfirmingRemoval(false)}
          open={confirmingRemoval}
          title="הסרת השורה?"
        >
          <p dir="auto">
            {removal.route === "selection"
              ? "הפעולה מחריגה את העובדה שמאחורי השורה ובונה את הטיוטה מחדש בלעדיה. אפשר לבטל את ההסרה זמן קצר לאחר מכן."
              : "השורה תוסר מהטיוטה. אפשר לבטל את ההסרה זמן קצר לאחר מכן."}
          </p>
        </Dialog>
      )}
    </li>
  );
};
