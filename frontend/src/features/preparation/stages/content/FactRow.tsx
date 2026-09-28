import { Check, Lock, Minus, Plus, Sparkles } from "lucide-react";
import { useId } from "react";

import type { Requirement } from "@/api/analyses";
import type { SelectionPlanCandidate } from "@/api/contracts";
import { cx } from "@/ui/cx";
import { candidateIncluded, candidateLocked } from "../../model/factGroups";
import { type FactRanking, type FactSignal, decisionSource, factSignals } from "../../model/selectionManifest";
import { decisionSourceLabels, omissionReasonLabels, selectionOutcomeLabels } from "../../model/selectionLabels";

export type FactChoice = "auto" | "include" | "exclude";

const choices: readonly { label: string; value: FactChoice }[] = [
  { label: "אוטומטי", value: "auto" },
  { label: "הכללה", value: "include" },
  { label: "החרגה", value: "exclude" },
];

const signalClasses: Record<FactSignal["tone"], string> = {
  positive: "bg-cv-success-soft text-cv-success",
  neutral: "bg-cv-surface-muted text-cv-text-muted",
  negative: "bg-cv-surface-muted text-cv-text-muted",
};

const outcomeSentence = (candidate: SelectionPlanCandidate): string =>
  candidate.reason == null
    ? selectionOutcomeLabels[candidate.outcome]
    : `${selectionOutcomeLabels[candidate.outcome]} · ${omissionReasonLabels[candidate.reason]}`;

const choiceFor = (factId: string, pinned: readonly string[], excluded: readonly string[]): FactChoice =>
  excluded.includes(factId) ? "exclude" : pinned.includes(factId) ? "include" : "auto";

export const FactRow = ({
  busy,
  candidate,
  change,
  excluded,
  onChoose,
  pinned,
  ranking,
  savedExcluded,
  savedPinned,
  supports,
}: {
  busy: boolean;
  candidate: SelectionPlanCandidate;
  change: "added" | "removed" | undefined;
  excluded: readonly string[];
  onChoose: (factId: string, choice: FactChoice) => void;
  pinned: readonly string[];
  ranking: FactRanking | undefined;
  savedExcluded: readonly string[];
  savedPinned: readonly string[];
  supports: readonly Requirement[];
}) => {
  const groupName = useId();
  const locked = candidateLocked(candidate);
  const included = candidateIncluded(candidate, pinned, excluded);
  const choice = choiceFor(candidate.fact_id, pinned, excluded);
  const pending = !locked && choice !== choiceFor(candidate.fact_id, savedPinned, savedExcluded);
  const source = decisionSource(candidate, pinned, excluded);
  const signals = factSignals(ranking, supports);
  const unreadable = candidate.text == null;
  const why =
    source === "pinned" || source === "excluded"
      ? decisionSourceLabels[source]
      : pending
        ? "תוחזר להחלטת המנוע בשמירה"
        : outcomeSentence(candidate);

  return (
    <li
      className={cx(
        "flex flex-col gap-2 border-t border-cv-border p-4",
        included ? "bg-cv-surface" : "bg-cv-surface-muted/60",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <p className={cx("min-w-0 flex-1 text-body", included ? "text-cv-text" : "text-cv-text-muted")} dir="auto">
          {candidate.text ?? "לא ניתן לקרוא את העובדה הזו מהידע."}
        </p>
        <span
          className={cx(
            "inline-flex shrink-0 items-center gap-1 rounded-pill px-2.5 py-0.5 text-caption font-semibold",
            locked
              ? "bg-cv-surface-muted text-cv-text-muted"
              : included
                ? "bg-cv-success-soft text-cv-success"
                : "bg-cv-surface-sunken text-cv-text-muted",
          )}
        >
          {locked ? (
            <Lock aria-hidden="true" className="size-icon-sm" />
          ) : included ? (
            <Check aria-hidden="true" className="size-icon-sm" />
          ) : (
            <Minus aria-hidden="true" className="size-icon-sm" />
          )}
          {locked ? "רכיב קבוע" : included ? "בקורות החיים" : "לא בקורות החיים"}
        </span>
      </div>

      {change === undefined ? null : (
        <p
          className={cx(
            "inline-flex w-fit items-center gap-1.5 rounded-control px-2 py-0.5 text-caption font-semibold",
            change === "added" ? "bg-cv-accent-soft text-cv-accent" : "bg-cv-warning-soft text-cv-warning",
          )}
        >
          <Sparkles aria-hidden="true" className="size-icon-sm" />
          {change === "added" ? "נוספה בהצעת ה־AI" : "הוסרה בהצעת ה־AI"}
        </p>
      )}

      <p className="text-support text-cv-text-muted">
        <span className="font-semibold text-cv-text">{why}</span>
        {pending ? <span className="text-cv-accent"> · שינוי שטרם נשמר</span> : null}
      </p>

      {signals.length === 0 ? null : (
        <ul aria-label="שיקולי הדירוג" className="flex flex-wrap gap-1.5">
          {signals.map((signal) => (
            <li
              className={cx("rounded-control px-2 py-0.5 text-caption", signalClasses[signal.tone])}
              key={signal.text}
            >
              {signal.text}
            </li>
          ))}
        </ul>
      )}

      {supports.length === 0 ? null : (
        <p className="text-caption text-cv-text-muted">
          עונה על:{" "}
          {supports.map((requirement, index) => (
            <span key={requirement.requirementId}>
              {index === 0 ? null : " · "}
              <bdi className="text-cv-text">{requirement.text}</bdi>
            </span>
          ))}
        </p>
      )}

      {locked ? null : (
        <fieldset className="flex flex-wrap items-center gap-2" disabled={busy || unreadable}>
          <legend className="sr-only">ההחלטה על העובדה</legend>
          <div className="inline-flex rounded-control border border-cv-border bg-cv-surface-muted p-0.5">
            {choices.map((option) => (
              <label
                className={cx(
                  "inline-flex min-h-8 cursor-pointer items-center gap-1 rounded-control px-3 text-support font-medium transition-colors has-[:disabled]:cursor-not-allowed has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-cv-focus",
                  choice === option.value
                    ? option.value === "exclude"
                      ? "bg-cv-surface text-cv-blocker shadow-surface"
                      : "bg-cv-surface text-cv-accent shadow-surface"
                    : "text-cv-text-muted hover:text-cv-text",
                )}
                key={option.value}
              >
                <input
                  checked={choice === option.value}
                  className="sr-only"
                  name={groupName}
                  onChange={() => onChoose(candidate.fact_id, option.value)}
                  type="radio"
                  value={option.value}
                />
                {option.value === "include" ? <Plus aria-hidden="true" className="size-icon-sm" /> : null}
                {option.value === "exclude" ? <Minus aria-hidden="true" className="size-icon-sm" /> : null}
                {option.label}
              </label>
            ))}
          </div>
        </fieldset>
      )}
    </li>
  );
};
