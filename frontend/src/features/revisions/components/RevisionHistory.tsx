import { useQueries } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronUp,
  Eye,
  FileCheck2,
  Flag,
  GitBranch,
  GitCompareArrows,
  History,
  LoaderCircle,
  type LucideIcon,
  RefreshCw,
  Send,
  Sparkles,
} from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link } from "react-router-dom";

import { revisionComparisonQueryOptions } from "@/api/revisions";
import { routePaths } from "@/app/routePaths";
import { Button, buttonClasses } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { SectionHeader } from "@/ui/SectionHeader";
import { StatusBadge } from "@/ui/StatusBadge";
import { cx } from "@/ui/cx";
import { formatDateTime } from "@/utils/formatDateTime";
import { changeSummaryPhrases, type RevisionHistoryEntry, type RevisionOrigin } from "../model/revisionHistory";

/* Enough to show what the reader has now and the few versions before it. Older ones are
   a press away, and the displayed one is never hidden behind that press. */
const COLLAPSED_COUNT = 4;

const originIcons: Record<RevisionOrigin, LucideIcon> = {
  first: Flag,
  reopened: GitBranch,
  rebuilt: RefreshCw,
};

const originText = (entry: RevisionHistoryEntry): string => {
  if (entry.origin === "first") return "הגרסה הראשונה שאושרה";
  if (entry.origin === "reopened") {
    return entry.base === null ? "נפתחה מגרסה קודמת" : `נפתחה מגרסה ${entry.base.version_number} ונערכה`;
  }
  return "נבנתה מחדש מניתוח המשרה";
};

const versionCountText = (count: number): string => (count === 1 ? "גרסה אחת" : `${count} גרסאות`);

const expandLabel = (showAll: boolean, hiddenCount: number): string => {
  if (showAll) return "הצגת הגרסאות האחרונות בלבד";
  return hiddenCount === 1 ? "הצגת גרסה קודמת אחת" : `הצגת ${hiddenCount} גרסאות קודמות`;
};

/* Which entries are on screen. An older displayed version forces the full list, so the
   toggle is only offered when collapsing would actually hide something the reader is
   not looking at. */
const useCollapsedEntries = (entries: RevisionHistoryEntry[]) => {
  const [expanded, setExpanded] = useState(false);
  const displayedIndex = entries.findIndex((entry) => entry.isDisplayed);
  const collapsible = entries.length > COLLAPSED_COUNT && displayedIndex < COLLAPSED_COUNT;
  const showAll = expanded || !collapsible;
  const visible = showAll ? entries : entries.slice(0, COLLAPSED_COUNT);

  return {
    collapsible,
    hiddenCount: entries.length - visible.length,
    showAll,
    toggle: () => setExpanded((value) => !value),
    visible,
  };
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
  const pending = phrases === undefined && !failed;
  const content =
    phrases === undefined
      ? failed
        ? "לא ניתן לחשב את השינויים כרגע."
        : "מחשב שינויים…"
      : phrases.length === 0
        ? `ללא שינוי בתוכן לעומת גרסה ${entry.base.version_number}`
        : phrases.join(" · ");

  return (
    <div className="mt-3 flex flex-col gap-1 border-s-2 border-cv-border-strong ps-3">
      {notes.length === 0 ? null : <p className="text-caption font-semibold text-cv-warning">{notes.join(" · ")}</p>}
      <p
        className={cx(
          "flex items-center gap-1.5 text-support leading-6",
          phrases === undefined ? "text-cv-text-muted" : "text-cv-text",
        )}
      >
        {pending ? <LoaderCircle aria-hidden="true" className="size-icon-sm shrink-0 animate-spin" /> : null}
        <span>{content}</span>
      </p>
    </div>
  );
};

interface TimelineMarkerProps {
  displayed: boolean;
  last: boolean;
  versionNumber: number;
}

/* The spine: one mark per version and a line to the one before it. The displayed
   version's mark is filled, so "which one am I looking at" reads from the spine as
   well as from the highlighted row. */
const TimelineMarker = ({ displayed, last, versionNumber }: TimelineMarkerProps) => (
  <div aria-hidden="true" className="flex w-8 shrink-0 flex-col items-center pt-3">
    <span
      className={cx(
        "flex size-8 shrink-0 items-center justify-center rounded-pill border-2 text-caption font-bold tabular-nums",
        displayed
          ? "border-cv-accent bg-cv-accent text-cv-on-accent"
          : "border-cv-border-strong bg-cv-surface text-cv-text-muted",
      )}
    >
      {versionNumber}
    </span>
    {last ? null : <span className="my-1 w-0.5 flex-1 rounded-pill bg-cv-border" />}
  </div>
);

interface RevisionEntryProps {
  entry: RevisionHistoryEntry;
  failed: boolean;
  last: boolean;
  phrases: string[] | undefined;
}

const RevisionEntry = ({ entry, failed, last, phrases }: RevisionEntryProps) => {
  const { base, revision } = entry;
  const OriginIcon = originIcons[entry.origin];

  return (
    <li aria-current={entry.isDisplayed ? "true" : undefined} className="relative flex gap-3">
      <TimelineMarker displayed={entry.isDisplayed} last={last} versionNumber={revision.version_number} />

      <article
        className={cx(
          "mb-3 min-w-0 flex-1 rounded-control border px-4 py-3 transition-colors",
          entry.isDisplayed
            ? "border-cv-border-strong bg-cv-surface-muted"
            : "border-cv-border bg-cv-surface hover:border-cv-border-strong",
        )}
      >
        <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-body font-bold text-cv-text">גרסה {revision.version_number}</h3>
            {entry.isLatest ? (
              <StatusBadge className="px-2.5 py-0.5" icon={Sparkles} tone="progress">
                העדכנית
              </StatusBadge>
            ) : null}
            {entry.isDisplayed ? (
              <StatusBadge className="px-2.5 py-0.5" icon={Eye} tone="neutral">
                מוצגת כעת
              </StatusBadge>
            ) : null}
          </div>
          <time className="text-caption text-cv-text-muted tabular-nums" dateTime={revision.approved_at}>
            אושרה {formatDateTime(revision.approved_at, "short")}
          </time>
        </header>

        <p className="mt-1.5 flex items-center gap-1.5 text-support text-cv-text-muted">
          <OriginIcon aria-hidden="true" className="size-icon-sm shrink-0" />
          <span>{originText(entry)}</span>
        </p>

        <div className="mt-2.5 flex flex-wrap gap-1.5">
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

        <ChangeLine entry={entry} failed={failed} phrases={phrases} />

        {entry.isDisplayed && base === null ? null : (
          <footer className="mt-3 flex flex-wrap gap-1 border-t border-cv-hairline pt-2">
            {entry.isDisplayed ? null : (
              <Link
                aria-label={`צפייה בגרסה ${revision.version_number}`}
                className={buttonClasses("ghost", "-ms-2.5", "compact")}
                to={routePaths.revision(revision.id)}
              >
                <Eye aria-hidden="true" className="size-icon-sm" />
                צפייה
              </Link>
            )}
            {base === null ? null : (
              <Link
                className={buttonClasses("ghost", entry.isDisplayed ? "-ms-2.5" : undefined, "compact")}
                to={routePaths.revisionComparison(revision.id, base.id)}
              >
                <GitCompareArrows aria-hidden="true" className="size-icon-sm" />
                השוואה לגרסה {base.version_number}
              </Link>
            )}
          </footer>
        )}
      </article>
    </li>
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
  const { collapsible, hiddenCount, showAll, toggle, visible } = useCollapsedEntries(entries);

  const comparisons = useQueries({
    queries: visible.map((entry) => ({
      ...revisionComparisonQueryOptions(entry.revision.id, entry.base?.id ?? ""),
      enabled: entry.base !== null,
    })),
  });

  return (
    <Card aria-labelledby="revision-history-heading" className="bg-cv-surface p-4 shadow-surface sm:p-5">
      <SectionHeader
        actions={
          <span className="rounded-pill border border-cv-border bg-cv-surface-muted px-2.5 py-0.5 text-caption font-semibold text-cv-text-muted">
            {versionCountText(entries.length)}
          </span>
        }
        description="כל אישור שומר גרסה קבועה שאינה משתנה עוד. אפשר לצפות בכל גרסה ולהשוות אותה לגרסה שלפניה."
        headingId="revision-history-heading"
        icon={History}
        title="היסטוריית גרסאות"
      />

      {nextDraft === undefined ? null : (
        <div className="mt-4 flex flex-col gap-2 rounded-control border border-dashed border-cv-border-strong bg-cv-surface-muted p-3">
          {nextDraft}
        </div>
      )}

      <ol className="mt-4 flex flex-col">
        {visible.map((entry, index) => {
          const comparison = comparisons[index];
          return (
            <RevisionEntry
              entry={entry}
              failed={comparison?.isError ?? false}
              key={entry.revision.id}
              last={index === visible.length - 1 && hiddenCount === 0}
              phrases={comparison?.data === undefined ? undefined : changeSummaryPhrases(comparison.data.summary)}
            />
          );
        })}
      </ol>

      {!collapsible ? null : (
        <Button aria-expanded={showAll} className="w-full" onClick={toggle} variant="ghost">
          {showAll ? (
            <ChevronUp aria-hidden="true" className="size-icon-sm" />
          ) : (
            <ChevronDown aria-hidden="true" className="size-icon-sm" />
          )}
          {expandLabel(showAll, hiddenCount)}
        </Button>
      )}
    </Card>
  );
};
