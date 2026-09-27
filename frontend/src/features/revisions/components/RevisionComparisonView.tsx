import { ArrowLeftRight, Info, Minus, PenLine, Plus } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import type { RevisionClaimChange, RevisionComparison, RevisionSectionComparison } from "@/api/contracts";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { EmptyState } from "@/ui/EmptyState";
import { LtrText } from "@/ui/LtrText";
import { StatusBadge } from "@/ui/StatusBadge";
import { cx } from "@/ui/cx";
import { changeSummaryPhrases, comparisonContextNotes } from "../model/revisionHistory";

const sectionName = (section: Pick<RevisionSectionComparison, "kind" | "name">) =>
  section.kind === "headline" ? "כותרת" : section.kind === "contacts" ? "פרטי קשר" : <LtrText>{section.name}</LtrText>;

const changePresentation: Record<RevisionClaimChange["kind"], { icon: LucideIcon; label: string }> = {
  added: { icon: Plus, label: "נוספה" },
  removed: { icon: Minus, label: "הוסרה" },
  reworded: { icon: PenLine, label: "נוסחה מחדש" },
  moved: { icon: ArrowLeftRight, label: "הועברה" },
};

/* The five counts across the top. Each is a number over its word rather than a chip, so
   the row reads as a tally a reader can take in at once. */
const SummaryTally = ({ comparison }: { comparison: RevisionComparison }) => {
  const items = [
    { label: "נוספו", value: comparison.summary.added },
    { label: "הוסרו", value: comparison.summary.removed },
    { label: "נוסחו מחדש", value: comparison.summary.reworded },
    { label: "הועברו", value: comparison.summary.moved },
    { label: "ללא שינוי", value: comparison.summary.unchanged },
  ];
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {items.map((item) => (
        <div className="rounded-control bg-cv-surface-muted px-3 py-2.5" key={item.label}>
          <dt className="text-support text-cv-text-muted">{item.label}</dt>
          <dd className={cx("text-heading-md font-bold", item.value === 0 ? "text-cv-text-muted" : "text-cv-text")}>
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
};

const ClaimText = ({ className, text }: { className?: string; text: string }) => (
  <p className={cx("text-body leading-7 text-cv-text", className)} dir="auto">
    {text}
  </p>
);

const ChangeRow = ({ change }: { change: RevisionClaimChange }) => {
  const { icon: Icon, label } = changePresentation[change.kind];
  const from =
    change.from_section == null ? null : change.from_section === "" ? null : <LtrText>{change.from_section}</LtrText>;

  return (
    <li className="flex gap-3 py-3 first:pt-0 last:pb-0">
      <span
        aria-hidden="true"
        className={cx(
          "mt-1 inline-flex size-6 shrink-0 items-center justify-center rounded-pill border",
          change.kind === "removed"
            ? "border-cv-border bg-cv-surface text-cv-text-muted"
            : "border-cv-accent/30 bg-cv-accent-soft text-cv-accent",
        )}
      >
        <Icon className="size-icon-sm" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-caption font-bold text-cv-text-muted">
          {label}
          {from === null ? null : <> מ־{from}</>}
        </p>
        {change.kind === "reworded" ? (
          <div className="mt-1.5 grid gap-2 md:grid-cols-2">
            <div className="rounded-control border border-cv-border px-3 py-2">
              <p className="mb-1 text-caption font-semibold text-cv-text-muted">לפני</p>
              <ClaimText className="text-cv-text-muted" text={change.before_text ?? ""} />
            </div>
            <div className="rounded-control border border-cv-border-strong bg-cv-surface-muted px-3 py-2">
              <p className="mb-1 text-caption font-semibold text-cv-text-muted">אחרי</p>
              <ClaimText text={change.after_text ?? ""} />
            </div>
          </div>
        ) : change.kind === "removed" ? (
          <ClaimText className="mt-0.5 text-cv-text-muted line-through" text={change.before_text ?? ""} />
        ) : (
          <ClaimText className="mt-0.5" text={change.after_text ?? ""} />
        )}
      </div>
    </li>
  );
};

const sectionStatusLabel: Partial<Record<RevisionSectionComparison["status"], string>> = {
  added: "סעיף חדש",
  removed: "הסעיף הוסר",
};

const SectionCard = ({ section }: { section: RevisionSectionComparison }) => {
  const status = sectionStatusLabel[section.status];
  return (
    <Card className="bg-cv-surface p-card-padding shadow-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-cv-border pb-3">
        <h3 className="text-body font-bold text-cv-text">{sectionName(section)}</h3>
        <div className="flex flex-wrap items-center gap-2">
          {status === undefined ? null : (
            <StatusBadge className="px-2.5 py-0.5" tone="neutral">
              {status}
            </StatusBadge>
          )}
          <span className="text-support text-cv-text-muted">
            {section.changes.length === 1 ? "שינוי אחד" : `${section.changes.length} שינויים`}
          </span>
        </div>
      </div>
      <ul className="mt-3 divide-y divide-cv-border">
        {section.changes.map((change, index) => (
          /* A comparison is a fixed list that never reorders, and two changes can carry
             identical text (a repeated date line), so position is the one stable key. */
          // oxlint-disable-next-line react/no-array-index-key
          <ChangeRow change={change} key={`${change.kind}-${index}`} />
        ))}
      </ul>
      {section.unchanged_count === 0 ? null : (
        <p className="mt-3 border-t border-cv-border pt-3 text-support text-cv-text-muted">
          {section.unchanged_count === 1
            ? "ועוד שורה אחת ללא שינוי בסעיף הזה."
            : `ועוד ${section.unchanged_count} שורות ללא שינוי בסעיף הזה.`}
        </p>
      )}
    </Card>
  );
};

export const RevisionComparisonView = ({ comparison }: { comparison: RevisionComparison }) => {
  const changed = comparison.sections.filter((section) => section.changes.length > 0);
  const unchanged = comparison.sections.filter((section) => section.changes.length === 0);
  const notes = comparisonContextNotes(comparison);
  const phrases = changeSummaryPhrases(comparison.summary);

  return (
    <div className="flex flex-col gap-section-gap">
      <section aria-labelledby="comparison-summary-heading" className="flex flex-col gap-3">
        <h2 className="text-heading-sm font-bold text-cv-text" id="comparison-summary-heading">
          {phrases.length === 0
            ? "אין שינוי בתוכן בין הגרסאות"
            : `מגרסה ${comparison.base_version_number} לגרסה ${comparison.target_version_number}: ${phrases.join(", ")}`}
        </h2>
        <SummaryTally comparison={comparison} />
        {notes.length === 0 ? null : (
          <Callout title="מה השתנה סביב התוכן" tone="info">
            <ul className="flex list-disc flex-col gap-0.5 ps-5">
              {notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </Callout>
        )}
      </section>

      {changed.length === 0 ? (
        <EmptyState>
          <Info aria-hidden="true" className="mx-auto size-icon-lg text-cv-text-muted" />
          <p className="mt-2 text-body font-semibold text-cv-text">כל השורות זהות בשתי הגרסאות.</p>
          <p className="mt-1 text-support text-cv-text-muted">
            ייתכן שהשתנה רק סדר הסעיפים או השורות, שאינו נחשב שינוי בתוכן.
          </p>
        </EmptyState>
      ) : (
        <section aria-labelledby="comparison-sections-heading" className="flex flex-col gap-3">
          <h2 className="sr-only" id="comparison-sections-heading">
            השינויים לפי סעיף
          </h2>
          {changed.map((section) => (
            <SectionCard key={`${section.kind}:${section.name}`} section={section} />
          ))}
        </section>
      )}

      {unchanged.length === 0 || changed.length === 0 ? null : (
        <p className="text-support text-cv-text-muted">
          ללא שינוי:{" "}
          {unchanged.map((section, index) => (
            <span key={`${section.kind}:${section.name}`}>
              {index === 0 ? null : " · "}
              {sectionName(section)}
            </span>
          ))}
        </p>
      )}
    </div>
  );
};
