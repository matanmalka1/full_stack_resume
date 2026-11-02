import { type ReactNode, useState } from "react";
import {
  ArrowDown,
  ArrowUp,
  BookOpen,
  Check,
  type LucideIcon,
  Pencil,
  RefreshCw,
  Trash2,
  TriangleAlert,
} from "lucide-react";

import type { DraftClaim, DraftFact } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { IconButton } from "@/ui/IconButton";
import { Callout } from "@/ui/Callout";
import { Dialog } from "@/ui/Dialog";
import { ReasonDetails } from "@/features/preparation";
import { DisclosureChevron } from "@/ui/Disclosure";
import { Textarea } from "@/ui/Input";
import { Tooltip } from "@/ui/Tooltip";
import { cx } from "@/ui/cx";
import type { DraftClaimActions } from "../model/drafts.types";
import type { Removability } from "../model/draftClaims";
import { claimTypeExplanations, claimTypeLabels } from "../model/draftLabels";

interface DraftClaimRowProps {
  actions: DraftClaimActions;
  /* The posting's requirements this line's facts answer, named on its status line. */
  answers?: string[];
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
    <IconButton
      aria-label={label}
      className="max-lg:size-9"
      disabled={disabled}
      onClick={onClick}
      size="sm"
      variant="quiet"
    >
      <Icon aria-hidden="true" className={cx("size-icon-md", className)} />
    </IconButton>
  </Tooltip>
);

/* The design's answers to a line waiting on the reader: small pills under it, the one
   that keeps it filled. */
const pillClasses = (filled: boolean) =>
  cx(
    "inline-flex h-8.5 items-center rounded-pill px-3.5 text-support font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-50 max-lg:h-8 max-lg:px-3 max-lg:text-caption",
    filled
      ? "bg-cv-accent text-cv-on-accent hover:bg-cv-accent-hover"
      : "border border-cv-border bg-cv-surface text-cv-text hover:bg-cv-surface-muted",
  );

/* Whether a line's source has anything to say that the line and its badge do not: a fact
   worded differently from the line, the evidence a reworded line was accepted on, or why
   the line cannot be removed. A contact copied verbatim from its fact has none, and a
   toggle that opens onto "identical" on every such row was noise. */
const hasSource = (claim: DraftClaim, facts: DraftFact[], removalReason: string | undefined): boolean =>
  removalReason !== undefined ||
  claim.review_evidence != null ||
  facts.some((fact) => fact.text !== claim.text) ||
  facts.length > 1;

/* Where the line came from, folded under the line: the fact behind it, how its wording
   relates to that fact, and - for reworded lines - the evidence the review accepted.

   This is the content swap the draft performed, made readable per line. It used to be a
   list of bullets printed under every row whether or not anyone asked, which on a
   sixty-line CV doubled the page. Its toggle sits on the row's status line, so a closed
   source costs no line of its own. */
const ClaimSourcePanel = ({
  claim,
  facts,
  id,
  open,
  removalReason,
}: {
  claim: DraftClaim;
  facts: DraftFact[];
  id: string;
  open: boolean;
  removalReason?: string;
}) => {
  const reviewAssertions = new Map(
    claim.review_evidence?.assertions.map(
      (assertion) =>
        [JSON.stringify([assertion.claim_quote, assertion.fact_ids, assertion.source_quotes]), assertion] as const,
    ) ?? [],
  );

  return (
    <div className="flex flex-col gap-2 border-s-2 border-cv-border ps-3 text-support leading-6" hidden={!open} id={id}>
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
  );
};

const NO_ANSWERS: string[] = [];

/* One line of the draft, as the design draws it: a bullet, the line's text, and under it
   one quiet status line - where the line came from and which requirement it answers. A
   line nothing authorizes is set on a recessed ground with what the check found and the
   reader's three answers to it. Computes nothing about the draft itself - removability
   and linked facts are the list's answers. */
export const DraftClaimRow = ({
  actions,
  answers = NO_ANSWERS,
  claim,
  factResolution,
  facts,
  move,
  removal,
}: DraftClaimRowProps) => {
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

  const [sourceOpen, setSourceOpen] = useState(false);
  /* Keeping a line nothing authorizes means giving it something to stand on: a check of
     its wording against the facts it names, or a fact made from it. The pill opens the
     two ways to do that under the line. */
  const [keeping, setKeeping] = useState(false);
  const sourceId = `draft-claim-source-${claim.claim_id}`;
  const keepId = `draft-claim-keep-${claim.claim_id}`;
  const removalReason = removal.route === "none" ? removal.reason : undefined;
  const pending = claim.claim_type === "pending";
  /* A pending line with nothing behind it has no source to open; its notice is the
     whole story. */
  const showSource = !(pending && facts.length === 0) && hasSource(claim, facts, removalReason);
  /* The headline and the contacts come from the Profile, whatever their claim type. */
  const sourceLabel =
    claim.style === "headline" || claim.style === "contact"
      ? claimTypeLabels.headline
      : claimTypeLabels[claim.claim_type];

  const editingReviewedClaim = claim.claim_type === "reviewed";
  /* A line linked to facts can be checked as written. The headline and the contacts are
     not factual claims, and an unlinked line has nothing to be checked against - it is
     resolved below, as a fact. */
  // Regeneration addresses section claims only; identity lines are edited manually.
  const regeneratable = claim.style !== "headline" && claim.style !== "contact";
  const reviewable = claim.fact_ids.length > 0 && regeneratable;

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
        "group/row flex scroll-mt-24 gap-3 border-t border-cv-hairline px-5 py-3.5 focus-visible:-outline-offset-2 max-lg:scroll-mt-20 max-lg:gap-2.5 max-lg:px-3.5 max-lg:py-3",
        pending && "bg-cv-canvas",
      )}
      id={`draft-claim-${claim.claim_id}`}
      tabIndex={-1}
    >
      <span aria-hidden="true" className="mt-2.25 size-1.5 shrink-0 rounded-pill bg-cv-text max-lg:mt-2" />
      <div className={cx("flex min-w-0 flex-1 flex-col", pending ? "gap-2.5 max-lg:gap-2" : "gap-1.5")}>
        {/* `text`, not `claim.text`: an edit still in the autosave buffer is what the user
            last typed. */}
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
          <p className="text-body leading-normal text-cv-text max-lg:text-label" dir="auto">
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
          {/* Where the line came from and what it answers. The origin opens the source
              panel when the source has more to say than the line itself. */}
          <p className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-caption text-cv-text-muted">
            {showSource ? (
              <button
                aria-controls={sourceId}
                aria-expanded={sourceOpen}
                className="inline-flex items-center gap-1 rounded-item font-medium transition-colors hover:text-cv-text"
                onClick={() => setSourceOpen(!sourceOpen)}
                type="button"
              >
                <BookOpen aria-hidden="true" className="size-icon-sm" />
                {sourceLabel}
                <DisclosureChevron className="size-icon-sm" open={sourceOpen} />
              </button>
            ) : (
              <span className="inline-flex items-center gap-1">
                {pending ? null : <BookOpen aria-hidden="true" className="size-icon-sm" />}
                {sourceLabel}
              </span>
            )}
            {answers.length === 0 ? null : (
              <>
                <span aria-hidden="true">·</span>
                <span dir="auto">
                  עונה על {answers[0]}
                  {answers.length > 1 ? ` ועוד ${answers.length - 1}` : ""}
                </span>
              </>
            )}
          </p>

          {/* Out of the way until the row is pointed at or focused, as the design draws a
              line: sixty rows of five icons read as a toolbar, not a document. On a wide
              screen they are always present and focusable, only faded out, and take no
              height of their own from the status line. A phone has no pointer to hover
              with, so there they appear once the row is tapped - the row takes focus - or
              tabbed into: until then they are visually hidden, not removed, so the Tab key
              and assistive tech still reach them. A line waiting on the reader is edited
              and removed through its pills instead. */}
          <div className="flex items-center gap-0.5 transition-opacity lg:-my-2 lg:opacity-0 lg:group-focus-within/row:opacity-100 lg:group-hover/row:opacity-100 max-lg:sr-only max-lg:group-focus-within/row:not-sr-only">
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
            {pending ? null : (
              <RowAction
                className={editing ? "text-cv-accent" : undefined}
                disabled={actions.locked && !editing}
                icon={editing ? Check : Pencil}
                label={editing ? "סיום עריכת השורה" : "עריכת השורה"}
                onClick={toggleEditing}
              />
            )}
            {regeneratable ? (
              <RowAction
                disabled={actions.regenerationDisabled}
                icon={RefreshCw}
                label="יצירה מחדש של השורה"
                onClick={() => actions.onRegenerate(claim)}
              />
            ) : null}
            {pending || removal.route === "none" ? null : (
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
            <div className="flex items-start gap-2 rounded-control-sm bg-cv-surface-muted px-2.5 py-2 text-support leading-snug font-medium text-cv-text">
              <TriangleAlert aria-hidden="true" className="mt-0.5 size-icon-md shrink-0" />
              <div className="min-w-0">
                <p>
                  {claim.pending_reason == null
                    ? "אין עובדה שמאשרת את השורה הזו, והיא חוסמת את אישור הטיוטה עד שתוכרע."
                    : "הבדיקה מצאה טענה שאינה נתמכת בעובדות. ניסוח חדש ייבדק שוב."}
                </p>
                {claim.pending_reason == null ? null : <ReasonDetails message={claim.pending_reason} />}
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <button
                aria-controls={keepId}
                aria-expanded={keeping}
                className={pillClasses(true)}
                disabled={actions.locked}
                onClick={() => setKeeping(!keeping)}
                type="button"
              >
                השארה
              </button>
              <button
                className={pillClasses(false)}
                disabled={actions.locked && !editing}
                onClick={toggleEditing}
                type="button"
              >
                {editing ? "סיום" : "עריכה"}
              </button>
              {removal.route === "none" ? null : (
                <button
                  className={pillClasses(false)}
                  disabled={actions.locked}
                  onClick={() => setConfirmingRemoval(true)}
                  type="button"
                >
                  הסרה
                </button>
              )}
            </div>
            <div className="flex flex-col gap-2.5" hidden={!keeping} id={keepId}>
              <p className="text-support leading-6 text-cv-text-muted">{claimTypeExplanations.pending}</p>
              {reviewable ? (
                <div className="flex flex-col items-start gap-1.5">
                  <Button
                    disabled={actions.regenerationDisabled}
                    onClick={() => actions.onReview(claim)}
                    variant="secondary"
                  >
                    בדיקת הניסוח מול העובדות
                  </Button>
                  <p className="text-caption text-cv-text-muted">
                    אם המשמעות זהה לעובדות שמאחוריה, הבדיקה תאשר את השורה בלי לשנות אותה.
                  </p>
                </div>
              ) : null}
              {factResolution}
            </div>
          </>
        ) : null}

        {showSource ? (
          <ClaimSourcePanel claim={claim} facts={facts} id={sourceId} open={sourceOpen} removalReason={removalReason} />
        ) : null}
      </div>

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
          /* A two-answer question about one line, not a sheet of content: on a phone it
             asks in the middle of the screen, over the row it is about. */
          presentation="alert"
          title="הסרת השורה?"
        >
          <p dir="auto">השורה תוסר מהטיוטה. אפשר לבטל את ההסרה זמן קצר לאחר מכן.</p>
        </Dialog>
      )}
    </li>
  );
};
