import { History, Undo2 } from "lucide-react";
import { useState } from "react";

import type { DocumentOutline } from "@/api/documents";
import { Button } from "@/ui/Button";
import { DisclosureSummary } from "@/ui/Disclosure";
import { StatusBadge } from "@/ui/StatusBadge";
import {
  type RegenerationChange,
  type RegenerationChangeState,
  type RegenerationTarget,
  changeState,
} from "../model/regenerationDiff";

interface RegenerationDiffPanelProps {
  changes: RegenerationChange[];
  /* Every command that changes the draft waits while a run is live. */
  locked: boolean;
  onDismiss: () => void;
  onRevert: (change: RegenerationChange) => void;
  /* The draft on screen, unsaved edits included: whether a line can still be reverted is
     read against it. */
  outline: DocumentOutline;
  target: RegenerationTarget | null;
}

const stateNotes: Record<Exclude<RegenerationChangeState, "regenerated">, string> = {
  reverted: "הוחזר לנוסח הקודם",
  edited: "נערך מאז היצירה מחדש",
  gone: "השורה כבר אינה בטיוטה",
};

const ChangeRow = ({
  change,
  locked,
  onRevert,
  outline,
}: {
  change: RegenerationChange;
  locked: boolean;
  onRevert: (change: RegenerationChange) => void;
  outline: DocumentOutline;
}) => {
  const state = changeState(change, outline);
  return (
    <li className="flex flex-col gap-2 py-3">
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <span className="text-caption font-semibold text-cv-text-muted">לפני</span>
          <p className="text-support leading-6 text-cv-text-muted line-through" dir="auto">
            {change.before.text}
          </p>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-caption font-semibold text-cv-text-muted">אחרי</span>
          <p className="text-support leading-6 text-cv-text" dir="auto">
            {change.after.text}
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2">
        {state === "regenerated" ? (
          <Button
            aria-label={`החזרת הנוסח הקודם: ${change.before.text}`}
            disabled={locked}
            onClick={() => onRevert(change)}
            variant="secondary"
          >
            <Undo2 aria-hidden="true" className="size-icon-md" />
            החזרת הנוסח הקודם
          </Button>
        ) : (
          <StatusBadge tone={state === "reverted" ? "success" : "neutral"}>{stateNotes[state]}</StatusBadge>
        )}
      </div>
    </li>
  );
};

/* The last regeneration this screen queued, each line it rewrote shown before and after,
   with a way back to the earlier wording.

   A revert is an ordinary edit through the autosave queue, so the server's content checks
   decide what the line becomes, exactly as for typed text (§10, §10.1): wording that the
   facts do not prove deterministically returns as a pending line, and needs the review
   again before approval. The panel says so rather than promising the old line's status
   back. Silent when the run changed no wording. */
export const RegenerationDiffPanel = ({
  changes,
  locked,
  onDismiss,
  onRevert,
  outline,
  target,
}: RegenerationDiffPanelProps) => {
  const [open, setOpen] = useState(true);
  if (changes.length === 0 || target === null) return null;
  const subject =
    target.kind === "section" ? (
      <>
        {" "}
        בסעיף <bdi>{target.section}</bdi>
      </>
    ) : null;

  return (
    <section
      aria-labelledby="regeneration-diff-heading"
      className="flex flex-col gap-2 border border-cv-border border-s-4 border-s-cv-accent bg-cv-surface p-card-padding max-lg:rounded-surface max-lg:p-3.5"
    >
      <details onToggle={(event) => setOpen(event.currentTarget.open)} open={open}>
        <DisclosureSummary className="text-body font-semibold text-cv-text max-lg:min-h-11" open={open}>
          <span className="inline-flex items-center gap-2" id="regeneration-diff-heading">
            <History aria-hidden="true" className="size-icon-md text-cv-text-muted" />
            {changes.length === 1 ? "היצירה מחדש שינתה שורה אחת" : `היצירה מחדש שינתה ${changes.length} שורות`}
            {subject}
          </span>
        </DisclosureSummary>
        <p className="mt-2 text-support leading-6 text-cv-text-muted">
          החזרה שולחת את הנוסח הקודם כעריכה רגילה. השרת בודק אותו מחדש מול העובדות: נוסח שאינו נגזר מהן ישירות יסומן
          כממתין לבדיקה.
        </p>
        <ul className="flex flex-col divide-y divide-cv-border">
          {changes.map((change) => (
            <ChangeRow change={change} key={change.claimId} locked={locked} onRevert={onRevert} outline={outline} />
          ))}
        </ul>
      </details>
      <div className="flex justify-end">
        <Button onClick={onDismiss} variant="ghost">
          סגירת ההשוואה
        </Button>
      </div>
    </section>
  );
};
