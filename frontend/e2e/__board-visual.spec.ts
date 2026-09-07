import { expect, test } from "@playwright/test";

const settings = {
  edit_version: 0,
  auto_generate_when_review_not_required: false,
  ai_enabled: false,
  ai_enabled_override: null,
  default_execution_mode: "deterministic",
  provider_configured: false,
  ui_density: "comfortable",
  ui_text_size: "normal",
  updated_at: null,
};

const base = {
  notes: "",
  source: "manual",
  working_draft_state: "none",
  review_reasons: [],
  stale_reasons: [],
  warnings: [],
  active_job_snapshot_id: "snap-1",
  newer_draft_in_progress: false,
  available_actions: ["analyze"],
  blocked_actions: [],
  recommended_action: "analyze",
  is_closed: false,
  created_at: "2026-08-24T07:00:00Z",
  updated_at: "2026-09-05T08:00:00Z",
};

const reason = (code: string) => ({ code, message: `יש פער חוסם מול הדרישות`, entity_references: {}, allowed_resolution_actions: [] });

const items = [
  { ...base, id: "app-1", company: "Acme", target_role: "Backend Engineer", current_status: "interview", recruitment_status: "interview", preparation_state: "ready", next_action: "Follow up with recruiter", next_action_date: "2026-09-01", latest_ready_revision_id: "rev-1" },
  { ...base, id: "app-2", company: "Binat", target_role: "Platform Engineer", current_status: "saved", recruitment_status: "saved", preparation_state: "needs_analysis", review_reasons: [reason("blocking_gap")] },
  { ...base, id: "app-3", company: "Cognyte", target_role: "Senior Fullstack Developer", current_status: "recruiter_screen", recruitment_status: "recruiter_screen", preparation_state: "draft_in_progress", next_action: "לשלוח מטלה", next_action_date: "2026-09-07" },
  { ...base, id: "app-4", company: "Deel", target_role: "Data Engineer", current_status: "assignment", recruitment_status: "assignment", preparation_state: "ready", latest_ready_revision_id: "rev-4" },
  { ...base, id: "app-5", company: "Elbit", target_role: "DevOps Engineer", current_status: "offer", recruitment_status: "offer", preparation_state: "approved" },
];

const listBody = {
  items,
  matched: items.length,
  total: 34,
  limit: 25,
  offset: 0,
  preset_counts: { all: 34, active_interviews: 8, ready_to_send: 3, needs_attention: 5 },
  recruitment_status_counts: { saved: 6, recruiter_screen: 4, interview: 3, assignment: 2, offer: 1, rejected: 12 },
  stage_counts: { needs_analysis: 9, draft_in_progress: 4, ready: 3, approved: 2 },
};

test("board", async ({ page }) => {
  await page.route("**/api/v1/settings", (route) => route.fulfill({ contentType: "application/json", json: settings }));
  await page.route("**/api/v1/applications**", (route) => route.fulfill({ contentType: "application/json", json: listBody }));
  page.on("console", (m) => console.log("CONSOLE", m.type(), m.text()));
  page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
  await page.goto("/");
  await page.waitForTimeout(1500);
  console.log(await page.locator("main").innerText());
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.screenshot({ path: "/private/tmp/claude-501/-Users-matanmalka-Projects-resume-python/35527bac-d3ea-4e47-b781-525f4f392267/scratchpad/board-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 900, height: 1100 });
  await page.screenshot({ path: "/private/tmp/claude-501/-Users-matanmalka-Projects-resume-python/35527bac-d3ea-4e47-b781-525f4f392267/scratchpad/board-tablet.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 900 });
  await page.screenshot({ path: "/private/tmp/claude-501/-Users-matanmalka-Projects-resume-python/35527bac-d3ea-4e47-b781-525f4f392267/scratchpad/board-mobile.png", fullPage: true });
});
