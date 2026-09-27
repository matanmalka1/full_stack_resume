import { describe, expect, it } from "vitest";

import type { RecruitmentTimelineItem } from "@/api/contracts";
import { revision, revisionComparison } from "@/test/fixtures";
import { buildRevisionHistory, changeSummaryPhrases, comparisonContextNotes } from "./revisionHistory";

const submission = (approvedRevisionId: string, occurredAt: string) =>
  ({
    id: `submission-${occurredAt}`,
    item_type: "submission",
    approved_revision_id: approvedRevisionId,
    occurred_at: occurredAt,
  }) as RecruitmentTimelineItem;

describe("buildRevisionHistory", () => {
  it("orders newest first and compares each version with its parent, else the one before it", () => {
    const entries = buildRevisionHistory(
      [
        revision({ id: "r3", version_number: 3, job_analysis_id: "analysis-2" }),
        revision({ id: "r1", version_number: 1 }),
        revision({ id: "r2", version_number: 2, parent_revision_id: "r1", job_snapshot_id: "snapshot-2" }),
        revision({ id: "r4", version_number: 4, parent_revision_id: "r2", job_analysis_id: "analysis-2" }),
      ],
      "r2",
      [submission("r2", "2026-08-01T00:00:00Z"), submission("r2", "2026-08-03T00:00:00Z")],
    );

    expect(entries.map((entry) => [entry.revision.id, entry.base?.id ?? null, entry.origin])).toEqual([
      /* r4 was reopened from r2, so it is compared with r2 rather than with r3. */
      ["r4", "r2", "reopened"],
      ["r3", "r2", "rebuilt"],
      ["r2", "r1", "reopened"],
      ["r1", null, "first"],
    ]);
    expect(entries.map((entry) => entry.isLatest)).toEqual([true, false, false, false]);
    expect(entries.find((entry) => entry.isDisplayed)?.revision.id).toBe("r2");
    expect(entries[2]).toMatchObject({ jobSnapshotChanged: true, analysisChanged: false });
    expect(entries[1]).toMatchObject({ jobSnapshotChanged: true, analysisChanged: true });
    expect(entries[2]?.submittedAt).toBe("2026-08-03T00:00:00Z");
    expect(entries[0]?.submittedAt).toBeNull();
  });
});

describe("change phrases", () => {
  it("names each non-zero count in Hebrew with singular forms, and nothing when unchanged", () => {
    expect(changeSummaryPhrases({ added: 1, removed: 3, reworded: 0, moved: 1, unchanged: 9 })).toEqual([
      "שורה אחת נוספה",
      "3 שורות הוסרו",
      "שורה אחת הועברה",
    ]);
    expect(changeSummaryPhrases({ added: 0, removed: 0, reworded: 0, moved: 0, unchanged: 9 })).toEqual([]);
  });

  it("explains a changed plan through the new analysis rather than twice", () => {
    expect(
      comparisonContextNotes(
        revisionComparison({ job_analysis_changed: true, selection_plan_changed: true, profile_changed: true }),
      ),
    ).toEqual(["הגרסה החדשה נבנתה מניתוח משרה אחר", "הפרופיל התעסוקתי השתנה"]);
  });
});
