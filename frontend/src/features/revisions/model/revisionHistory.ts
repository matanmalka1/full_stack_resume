import type {
  ApprovedRevision,
  RecruitmentTimelineItem,
  RevisionChangeSummary,
  RevisionComparison,
} from "@/api/contracts";

/* How a revision came to exist, which is the first thing a reader needs to place it:
   - "first": the Application's first approval;
   - "reopened": its draft was reopened from an earlier revision and edited;
   - "rebuilt": its draft was composed fresh from an analysis, not from a revision. */
export type RevisionOrigin = "first" | "reopened" | "rebuilt";

export interface RevisionHistoryEntry {
  revision: ApprovedRevision;
  /* What this revision is compared against by default: the revision its draft was
     reopened from, or else the version immediately before it. `null` only for the first. */
  base: ApprovedRevision | null;
  origin: RevisionOrigin;
  /* Known from the two records alone, before any comparison is fetched. */
  jobSnapshotChanged: boolean;
  analysisChanged: boolean;
  isLatest: boolean;
  isDisplayed: boolean;
  /* The latest recorded submission of exactly this revision. */
  submittedAt: string | null;
}

const latestSubmissionByRevision = (timeline: readonly RecruitmentTimelineItem[]): Map<string, string> => {
  const submitted = new Map<string, string>();
  for (const item of timeline) {
    if (item.item_type !== "submission" || item.approved_revision_id == null) continue;
    const previous = submitted.get(item.approved_revision_id);
    if (previous === undefined || item.occurred_at > previous) {
      submitted.set(item.approved_revision_id, item.occurred_at);
    }
  }
  return submitted;
};

/* Newest first: the reader opens history to find what they have now and what came
   just before it, not the Application's first approval. */
export const buildRevisionHistory = (
  revisions: readonly ApprovedRevision[],
  displayedRevisionId: string,
  timeline: readonly RecruitmentTimelineItem[] = [],
): RevisionHistoryEntry[] => {
  const ascending = [...revisions];
  // oxlint-disable-next-line unicorn/no-array-sort -- local copy; toSorted needs ES2023.
  ascending.sort((left, right) => left.version_number - right.version_number);
  const byId = new Map(ascending.map((revision) => [revision.id, revision]));
  const submitted = latestSubmissionByRevision(timeline);
  const latestId = ascending.at(-1)?.id;

  return (
    ascending
      .map((revision, index): RevisionHistoryEntry => {
        const parent = revision.parent_revision_id == null ? undefined : byId.get(revision.parent_revision_id);
        const base = parent ?? ascending[index - 1] ?? null;
        return {
          revision,
          base,
          origin: revision.parent_revision_id != null ? "reopened" : index === 0 ? "first" : "rebuilt",
          jobSnapshotChanged: base !== null && base.job_snapshot_id !== revision.job_snapshot_id,
          analysisChanged: base !== null && base.job_analysis_id !== revision.job_analysis_id,
          isLatest: revision.id === latestId,
          isDisplayed: revision.id === displayedRevisionId,
          submittedAt: submitted.get(revision.id) ?? null,
        };
      })
      // oxlint-disable-next-line unicorn/no-array-reverse -- fresh array from map; toReversed needs ES2023.
      .reverse()
  );
};

const count = (value: number, one: string, many: (value: number) => string): string =>
  value === 1 ? one : many(value);

/* The line changes as short Hebrew phrases, in the order a reader weighs them: what is
   new, what is gone, what was reworded, what only moved. Empty when nothing changed. */
export const changeSummaryPhrases = (summary: RevisionChangeSummary): string[] =>
  [
    summary.added === 0 ? null : count(summary.added, "שורה אחת נוספה", (n) => `${n} שורות נוספו`),
    summary.removed === 0 ? null : count(summary.removed, "שורה אחת הוסרה", (n) => `${n} שורות הוסרו`),
    summary.reworded === 0 ? null : count(summary.reworded, "שורה אחת נוסחה מחדש", (n) => `${n} שורות נוסחו מחדש`),
    summary.moved === 0 ? null : count(summary.moved, "שורה אחת הועברה", (n) => `${n} שורות הועברו`),
  ].filter((phrase): phrase is string => phrase !== null);

/* What changed around the content: the frozen inputs the newer revision was built from.
   Each one explains a batch of line changes the reader would otherwise have to infer. */
export const comparisonContextNotes = (comparison: RevisionComparison): string[] =>
  [
    comparison.job_snapshot_changed ? "נוסח מודעת המשרה עודכן בין הגרסאות" : null,
    comparison.job_analysis_changed ? "הגרסה החדשה נבנתה מניתוח משרה אחר" : null,
    comparison.selection_plan_changed && !comparison.job_analysis_changed ? "בחירת העובדות השתנתה" : null,
    comparison.facts_version_changed ? "מאגר העובדות עודכן בין הגרסאות" : null,
    comparison.profile_changed ? "הפרופיל התעסוקתי השתנה" : null,
    comparison.emphasis_changed ? "הדגש של קורות החיים השתנה" : null,
    comparison.language_changed ? "שפת קורות החיים השתנתה" : null,
  ].filter((note): note is string => note !== null);
