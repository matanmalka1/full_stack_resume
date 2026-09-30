import { Minus, Plus, Sparkles } from "lucide-react";

import type { Requirement } from "@/api/analyses";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { cx } from "@/ui/cx";
import { type SelectionChange, factSignals } from "../../model/selectionManifest";
import type { ProposalStatus } from "./useSelectionProposal";

/* How a proposal works, explained once in the selection panel's own "how" disclosure. */
export const aiProposalSteps = [
  "ה־AI מקבל את ניתוח המשרה (דרישות, פערים ומילות מפתח), את העובדות שהפרופיל מתיר ואת הבחירה שהמנוע כבר עשה.",
  "הוא מציע אילו עובדות להוסיף לבחירה ואילו להחריג ממנה - רק מתוך העובדות המאושרות, בלי לנסח או לשנות אותן.",
  "המנוע בונה מחדש את הבחירה לפי ההצעה ובודק אותה מול כללי הבחירה: מכסת כל סעיף, רכיבים קבועים וכיסוי התגיות שהפרופיל מחייב. הצעה שחורגת מהם נדחית, והבחירה הקודמת נשארת.",
  "הקיבועים וההחרגות הידניים הנוכחיים מוחלפים בהצעה. כל שינוי מסומן ברשימה ואפשר לבטל אותו.",
  "אם כבר יש טיוטה שהמנוע כתב, היא נבנית מחדש מהבחירה החדשה. טיוטה עם ניסוח ידני או של AI אינה מקבלת הצעה, כי בנייה מחדש הייתה מוחקת אותו.",
];

const ChangeList = ({
  changes,
  direction,
  supportsByFact,
}: {
  changes: readonly SelectionChange[];
  direction: SelectionChange["direction"];
  supportsByFact: ReadonlyMap<string, readonly Requirement[]>;
}) => {
  const items = changes.filter((change) => change.direction === direction);
  if (items.length === 0) {
    return null;
  }
  const Icon = direction === "added" ? Plus : Minus;

  return (
    <div>
      <h4 className="mb-2 flex items-center gap-1.5 text-support font-bold text-cv-text">
        <Icon
          aria-hidden="true"
          className={cx("size-icon-md", direction === "added" ? "text-cv-success" : "text-cv-warning")}
        />
        {direction === "added" ? `נוספו לקורות החיים (${items.length})` : `הוסרו מקורות החיים (${items.length})`}
      </h4>
      <ul className="flex flex-col gap-2">
        {items.map(({ candidate }) => {
          const supports = supportsByFact.get(candidate.fact_id) ?? [];
          const signals = factSignals(supports);
          return (
            <li className="rounded-control border border-cv-border bg-cv-surface p-3" key={candidate.fact_id}>
              <p className="text-support text-cv-text" dir="auto">
                {candidate.text ?? "לא ניתן לקרוא את העובדה הזו מהידע."}
              </p>
              <p className="mt-1 text-caption text-cv-text-muted">
                <bdi>{candidate.section}</bdi>
                {signals.length === 0 ? null : ` · ${signals.map((signal) => signal.text).join(" · ")}`}
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export const AiSelectionProposal = ({
  aiAvailable,
  authoredWording,
  busy,
  changes,
  hasContent,
  offered,
  onDismiss,
  onPropose,
  pending,
  rationale,
  resultVisible,
  settingsLoaded,
  status,
  supportsByFact,
}: {
  aiAvailable: boolean;
  /* The stage withholds a proposal because the draft carries manual or AI wording (§14),
     as opposed to a blocker such as live work, which the projection reports separately. */
  authoredWording: boolean;
  busy: boolean;
  changes: readonly SelectionChange[];
  /* The document already has a draft, which an activated proposal rebuilds. */
  hasContent: boolean;
  /* The projection offers `propose_selection` now. Whether it does is the server's answer
     (§9); this panel only says so. */
  offered: boolean;
  onDismiss: () => void;
  onPropose: () => void;
  pending: boolean;
  /* The selection's recorded AI rationale: undefined when the selection did not come from
     an AI proposal, null when the proposal gave none. */
  rationale: string | null | undefined;
  resultVisible: boolean;
  settingsLoaded: boolean;
  status: ProposalStatus;
  supportsByFact: ReadonlyMap<string, readonly Requirement[]>;
}) => (
  <section
    aria-labelledby="ai-selection-heading"
    className="flex flex-col gap-3 rounded-surface border border-cv-accent/30 bg-cv-accent-soft/40 p-4"
  >
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0 flex-1">
        <h3 className="flex items-center gap-1.5 text-body font-semibold text-cv-text" id="ai-selection-heading">
          <Sparkles aria-hidden="true" className="size-icon-md text-cv-accent" />
          הצעת בחירה באמצעות AI
        </h3>
        {/* The cost and the rebuild describe the press, so they stand only beside the button. */}
        {aiAvailable && offered ? (
          <p className="mt-1 text-support text-cv-text-muted">
            ההצעה כוללת קריאת AI בתשלום.{hasContent ? " הטיוטה תיבנה מחדש מהבחירה החדשה." : null}
          </p>
        ) : null}
      </div>
      {aiAvailable && offered ? (
        <Button
          disabled={busy || !settingsLoaded || status.kind === "running"}
          onClick={onPropose}
          pending={pending}
          pendingLabel="מבקש הצעת AI…"
          variant="secondary"
        >
          הצעת בחירה באמצעות AI
        </Button>
      ) : null}
    </div>

    {!aiAvailable && settingsLoaded ? (
      <p className="text-support text-cv-text-muted">הצעת AI זמינה לאחר הגדרת ספק AI.</p>
    ) : aiAvailable && !offered ? (
      <p className="text-support text-cv-text-muted">
        {authoredWording
          ? "הטיוטה כוללת ניסוח ידני או של AI, ובנייה מחדש מבחירה חדשה הייתה מוחקת אותו. אפשר לשנות אותה בעורך, ביצירה מחדש של סעיף או שורה."
          : "הצעת AI אינה זמינה למסמך במצבו הנוכחי."}
      </p>
    ) : null}

    {rationale === undefined ? null : (
      <div className="rounded-control bg-cv-surface p-3">
        <h4 className="text-support font-bold text-cv-text">נימוק הצעת ה־AI</h4>
        {rationale === null ? (
          <p className="mt-1 text-support text-cv-text-muted">ההצעה לא כללה נימוק כתוב.</p>
        ) : (
          <p className="mt-1 whitespace-pre-line text-support text-cv-text" dir="auto">
            {rationale}
          </p>
        )}
      </div>
    )}

    {status.kind === "running" ? (
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      <Callout role="status" title="ה־AI בוחן את העובדות מול דרישות המשרה…" tone="progress">
        הבחירה הנוכחית נשארת בתוקף עד שההצעה תיבדק ותאושר על ידי המנוע.
      </Callout>
    ) : null}

    {status.kind === "failed" || status.kind === "unknown" ? (
      <Callout
        action={
          <Button onClick={onDismiss} variant="ghost">
            סגירת ההודעה
          </Button>
        }
        title={status.kind === "failed" ? "ההצעה לא התקבלה" : "לא ניתן לקרוא את תוצאת ההצעה"}
        tone="warning"
      >
        הבחירה הקודמת נשארה בתוקף. אפשר לבקש הצעה חדשה.
      </Callout>
    ) : null}

    {status.kind === "done" && resultVisible ? (
      <div className="flex flex-col gap-3 rounded-control bg-cv-surface p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-support font-bold text-cv-text">
            {changes.length === 0
              ? "ההצעה לא שינתה אילו עובדות נכנסות לקורות החיים."
              : `ההצעה שינתה ${changes.length === 1 ? "עובדה אחת" : `${changes.length} עובדות`} בקורות החיים:`}
          </p>
          <Button onClick={onDismiss} variant="ghost">
            סגירה
          </Button>
        </div>
        <ChangeList changes={changes} direction="added" supportsByFact={supportsByFact} />
        <ChangeList changes={changes} direction="removed" supportsByFact={supportsByFact} />
        {changes.length === 0 ? null : (
          <p className="text-caption text-cv-text-muted">
            השינויים מסומנים גם ברשימת העובדות למטה, ואפשר להחזיר כל עובדה להחלטת המנוע או לשנות אותה ידנית.
          </p>
        )}
      </div>
    ) : null}
  </section>
);
