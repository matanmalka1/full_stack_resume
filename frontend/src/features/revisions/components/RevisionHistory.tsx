import { useQueries } from "@tanstack/react-query";
import { FileCheck2, GitCompareArrows, History, Send } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link } from "react-router-dom";

import { revisionComparisonQueryOptions } from "@/api/revisions";
import { routePaths } from "@/app/routePaths";
import { Button, buttonClasses } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { StatusBadge } from "@/ui/StatusBadge";
import { cx } from "@/ui/cx";
import { formatDateTime } from "@/utils/formatDateTime";
import { changeSummaryPhrases, type RevisionHistoryEntry } from "../model/revisionHistory";

/* Enough to show what the reader has now and the few versions before it. Older ones are
   a press away, and the displayed one is never hidden behind that press. */
const COLLAPSED_COUNT = 4;

const originText = (entry: RevisionHistoryEntry): string => {
  if (entry.origin === "first") return "הגרסה הראשונה שאושרה";
  if (entry.origin === "reopened") {
    return entry.base === null ? "נפתחה מגרסה קודמת" : `נפתחה מגרסה ${entry.base.version_number} ונערכה`;
  }
  return "נבנתה מחדש מניתוח המשרה";
};

interface ChangeLineProps {
  entry: RevisionHistoryEntry;
  phrases: string[] | undefined;
  failed: boolean;
}

/* The one line that answers "what is different in this version". The two context notes
   come from the records themselves and show at once; the line changes wait for the
   comparison, and say so rather than holding an empty gap. */
const ChangeLine = ({ entry, failed, phrases }: ChangeLineProps) => {
  if (entry.base === null) return null;
  const notes = [
    entry.jobSnapshotChanged ? "נוסח המשרה עודכן" : null,
    entry.analysisChanged && !entry.jobSnapshotChanged ? "ניתוח חדש" : null,
  ].filter((note): note is string => note !== null);
  const content =
    phrases === undefined
      ? failed
        ? "לא ניתן לחשב את השינויים כרגע."
        : "מחשב שינויים…"
      : phrases.length === 0
        ? `ללא שינוי בתוכן לעומת גרסה ${entry.base.version_number}`
        : phrases.join(" · ");

  return (
    <div className="mt-1.5 flex flex-col gap-1">
      {notes.length === 0 ? null : <p className="text-caption font-semibold text-cv-warning">{notes.join(" · ")}</p>}
      <p className={cx("text-support leading-6", phrases === undefined ? "text-cv-text-muted" : "text-cv-text")}>
        {content}
      </p>
    </div>
  );
};

interface RevisionHistoryProps {
  /* Newest first, as `buildRevisionHistory` returns them. */
  entries: RevisionHistoryEntry[];
  /* What can be done next from the displayed version: continue the active draft, or
     start a new one from this version. Drawn under the heading, above the list. */
  nextDraft?: ReactNode;
}

export const RevisionHistory = ({ entries, nextDraft }: RevisionHistoryProps) => {
  const [expanded, setExpanded] = useState(false);
  const displayedIndex = entries.findIndex((entry) => entry.isDisplayed);
  /* An older displayed version forces the full list, so the toggle is only offered when
     collapsing would actually hide something the reader is not looking at. */
  const collapsible = entries.length > COLLAPSED_COUNT && displayedIndex < COLLAPSED_COUNT;
  const showAll = expanded || !collapsible;
  const visible = showAll ? entries : entries.slice(0, COLLAPSED_COUNT);
  const hiddenCount = entries.length - visible.length;

  const comparisons = useQueries({
    queries: visible.map((entry) => ({
      ...revisionComparisonQueryOptions(entry.revision.id, entry.base?.id ?? ""),
      enabled: entry.base !== null,
    })),
  });

  return (
    <Card aria-labelledby="revision-history-heading" className="bg-cv-surface p-4 shadow-surface">
      <h2 className="flex items-center gap-2 font-semibold text-cv-text" id="revision-history-heading">
        <History aria-hidden="true" className="size-icon-md text-cv-accent" />
        היסטוריית גרסאות
      </h2>
      <p className="mt-1 text-support leading-6 text-cv-text-muted">
        כל אישור שומר גרסה קבועה שאינה משתנה עוד. אפשר לצפות בכל גרסה ולהשוות אותה לגרסה שלפניה.
      </p>
      {nextDraft === undefined ? null : <div className="mt-3 flex flex-col gap-2">{nextDraft}</div>}

      <ol className="mt-4 flex flex-col">
        {visible.map((entry, index) => {
          const { revision } = entry;
          const comparison = comparisons[index];
          const phrases = comparison?.data === undefined ? undefined : changeSummaryPhrases(comparison.data.summary);
          const last = index === visible.length - 1 && hiddenCount === 0;

          return (
            <li aria-current={entry.isDisplayed ? "true" : undefined} className="relative flex gap-3" key={revision.id}>
              {/* The spine: one mark per version and a line to the one before it. The
                  displayed version's mark is filled, so "which one am I looking at" reads
                  from the spine as well as from the highlighted row. */}
              <div aria-hidden="true" className="flex w-4 shrink-0 flex-col items-center pt-4">
                <span
                  className={cx(
                    "size-3 shrink-0 rounded-pill border-2",
                    entry.isDisplayed ? "border-cv-accent bg-cv-accent" : "border-cv-border-strong bg-cv-surface",
                  )}
                />
                {last ? null : <span className="mt-1 w-px flex-1 bg-cv-border" />}
              </div>

              <div
                className={cx(
                  "mb-2 min-w-0 flex-1 rounded-control px-3 py-2.5",
                  entry.isDisplayed ? "bg-cv-surface-muted" : undefined,
                )}
              >
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                  <h3 className="text-body font-bold text-cv-text">גרסה {revision.version_number}</h3>
                  {entry.isLatest ? <span className="text-caption font-semibold text-cv-accent">העדכנית</span> : null}
                  {entry.isDisplayed ? (
                    <span className="text-caption font-semibold text-cv-text-muted">· מוצגת כעת</span>
                  ) : null}
                </div>
                <p className="text-support text-cv-text-muted">
                  אושרה {formatDateTime(revision.approved_at, "short")} · {originText(entry)}
                </p>

                <div className="mt-2 flex flex-wrap gap-1.5">
                  {entry.submittedAt === null ? null : (
                    <StatusBadge className="px-2.5 py-0.5" icon={Send} tone="success">
                      הוגשה {formatDateTime(entry.submittedAt, "date")}
                    </StatusBadge>
                  )}
                  <StatusBadge
                    className="px-2.5 py-0.5"
                    icon={revision.ready_qualified ? FileCheck2 : undefined}
                    tone={revision.ready_qualified ? "success" : "neutral"}
                  >
                    {revision.ready_qualified ? "מוכנה למסירה" : "ללא קובץ PDF כשיר"}
                  </StatusBadge>
                </div>

                <ChangeLine entry={entry} failed={comparison?.isError ?? false} phrases={phrases} />

                <div className="mt-2 flex flex-wrap gap-1">
                  {entry.isDisplayed ? null : (
                    <Link
                      aria-label={`צפייה בגרסה ${revision.version_number}`}
                      className={buttonClasses("ghost", "-ms-2.5", "compact")}
                      to={routePaths.revision(revision.id)}
                    >
                      צפייה
                    </Link>
                  )}
                  {entry.base === null ? null : (
                    <Link
                      className={buttonClasses("ghost", entry.isDisplayed ? "-ms-2.5" : undefined, "compact")}
                      to={routePaths.revisionComparison(revision.id, entry.base.id)}
                    >
                      <GitCompareArrows aria-hidden="true" className="size-icon-sm" />
                      השוואה לגרסה {entry.base.version_number}
                    </Link>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>

      {!collapsible ? null : (
        <Button aria-expanded={showAll} onClick={() => setExpanded((value) => !value)} variant="ghost">
          {showAll
            ? "הצגת הגרסאות האחרונות בלבד"
            : hiddenCount === 1
              ? "הצגת גרסה קודמת אחת"
              : `הצגת ${hiddenCount} גרסאות קודמות`}
        </Button>
      )}
    </Card>
  );
};
