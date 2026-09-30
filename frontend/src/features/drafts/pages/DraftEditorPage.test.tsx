import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, CVDocument, DraftFact, FactDetail, Operation } from "@/api/contracts";
import type { DocumentOutline } from "@/api/documents";
import { settingsQueryKey } from "@/api/settings";
import { HASH, OTHER_HASH, cvDocument, detail as projection } from "@/test/fixtures";
import { DraftEditorPage } from "./DraftEditorPage";

const DOC_PATH = "/api/v1/applications/app-1/document";

/* A document hash per saved state, so a test can say which save a command was addressed
   to. Every one has the 64-hex shape the contract requires. */
const hashAt = (version: number): string => version.toString(16).padStart(64, "0");

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  projection({
    content_check: "none",
    available_actions: ["edit", "check", "approve"],
    recommended_action: "check",
    application: {
      id: "app-1",
      company: "Acme",
      target_role: "Account Manager",
      current_status: "saved",
      notes: "",
      created_at: "2026-08-24T07:00:00Z",
      updated_at: "2026-08-24T07:00:00Z",
    },
    ...overrides,
  });

const baseFacts = (): DraftFact[] => [
  {
    fact_id: "f-1",
    text: "Owned the CRM migration end to end.",
    linked_claim_ids: ["c-1"],
    section: "Core Skills",
    outcome: "selected",
    reason: null,
  },
  {
    fact_id: "f-mail",
    text: "matan@example.com",
    linked_claim_ids: ["c-mail"],
    section: null,
    outcome: null,
    reason: null,
  },
];

const baseOutline = (): DocumentOutline => ({
  headline: {
    claim_id: "c-headline",
    style: "headline",
    text: "Account Manager",
    claim_type: "headline",
    fact_ids: [],
    pending_reason: null,
  },
  contacts: [
    {
      claim_id: "c-mail",
      style: "contact",
      text: "matan@example.com",
      claim_type: "canonical",
      fact_ids: ["f-mail"],
      pending_reason: null,
    },
  ],
  sections: [
    {
      name: "Core Skills",
      claims: [
        {
          claim_id: "c-1",
          style: "bullet",
          text: "Owned the CRM migration.",
          claim_type: "canonical",
          fact_ids: ["f-1"],
          pending_reason: null,
        },
      ],
    },
  ],
});

/* The document the editor reads: content, outline and fact accounting in one read. It
   starts unchecked, so the finish action starts with the check. */
const draft = (outline: Partial<DocumentOutline> = {}, overrides: Partial<CVDocument> = {}): CVDocument =>
  cvDocument({
    content_check: "none",
    content_report: null,
    outline: { ...baseOutline(), ...outline },
    facts: baseFacts(),
    ...overrides,
  });

const firstClaim = () => baseOutline().sections[0]!.claims[0]!;

const jsonResponse = (body: unknown, status = 200, etag = `"${HASH}"`): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ETag: etag },
  });

const conflictResponse = (): Response =>
  new Response(
    JSON.stringify({
      type: "about:blank#document_changed",
      title: "Conflict",
      status: 409,
      code: "DOCUMENT_CHANGED",
      detail: "the document no longer has the hash the request named",
    }),
    { status: 409, headers: { "Content-Type": "application/problem+json" } },
  );

const updateResponse = (version: number): Response =>
  jsonResponse(
    {
      application_id: "app-1",
      document_id: "doc-1",
      document_hash: hashAt(version),
      preparation_state: "draft_in_progress",
      content_check: "none",
      pending_claim_ids: [],
    },
    200,
    `"${hashAt(version)}"`,
  );

const checkResponse = (documentHash: string, passed: boolean, issues: unknown[] = []): Response =>
  jsonResponse({
    application_id: "app-1",
    document_id: "doc-1",
    document_hash: documentHash,
    preparation_state: "draft_in_progress",
    content_check: passed ? "passed" : "failed",
    pending_claim_ids: [],
    passed,
    report: { passed, groups: {}, evidence: {}, issues },
    approved_at: null,
  });

const isDocumentRead = (url: string, init?: RequestInit) => url === DOC_PATH && (init?.method ?? "GET") === "GET";

/* One route per read, so a test states which answer it is giving rather than depending on
   the order the screen happens to request them in. */
const stubReads = (
  answers: Partial<
    Record<
      "detail" | "document" | "operation" | "selection" | "regenerate" | "check" | "render",
      () => Response | Promise<Response>
    >
  >,
): ReturnType<typeof vi.fn> => {
  const fetchMock = vi.fn((input: unknown, init?: RequestInit) => {
    const url = String(input);

    if (url.includes("/regenerate-")) {
      return Promise.resolve(answers.regenerate?.() ?? jsonResponse({}, 500));
    }
    if (url.startsWith("/api/v1/operations/")) {
      return Promise.resolve(answers.operation?.() ?? jsonResponse({}, 404));
    }
    if (url === `${DOC_PATH}/selection`) {
      return Promise.resolve(answers.selection?.() ?? updateResponse(5));
    }
    if (url === `${DOC_PATH}/render`) {
      return Promise.resolve(answers.render?.() ?? jsonResponse({}, 500));
    }
    if (url === `${DOC_PATH}/check`) {
      return Promise.resolve(answers.check?.() ?? jsonResponse({}, 500));
    }
    if (url === "/api/v1/facts" || url === "/api/v1/facts/history") {
      return Promise.resolve(jsonResponse(url.endsWith("/history") ? { events: [] } : { items: [] }));
    }
    if (isDocumentRead(url, init)) {
      return Promise.resolve(answers.document?.() ?? jsonResponse(draft()));
    }
    return Promise.resolve(answers.detail?.() ?? jsonResponse(detail()));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

const reviewDetail = (codes = ["PENDING_FACT_REQUIRES_RESOLUTION"]): ApplicationDetail =>
  detail({
    review_reasons: codes.map((code) => ({
      code,
      message: `Reason: ${code}`,
      entity_references: {},
      allowed_resolution_actions: code === "PENDING_FACT_REQUIRES_RESOLUTION" ? ["confirm_and_use_fact", "edit"] : [],
    })),
  });

const renderPage = (aiEnabled = true, search = "") => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  client.setQueryData(settingsQueryKey, {
    settings: {
      edit_version: 0,
      auto_generate_when_review_not_required: false,
      ai_enabled: aiEnabled,
      ai_enabled_override: aiEnabled,
      default_execution_mode: "deterministic",
      default_ai_model: "gpt-5.6-terra",
      default_reasoning_effort: "medium",
      available_ai_models: [],

      provider_configured: aiEnabled,
      ui_density: "comfortable",
      ui_text_size: "normal",
      ui_theme: "system",
      updated_at: null,
    },
    etag: '"settings-0"',
  });

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/applications/app-1/draft${search}`]}>
        <Routes>
          <Route element={<DraftEditorPage />} path="/applications/:applicationId/draft" />
          <Route element={<h1>הכנת קורות החיים</h1>} path="/applications/:applicationId" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

/* The screen shows the draft as text; a line becomes a field when its own pencil is
   pressed. Tests that type into a line open that line first, the way a user does. */
const editRow = async (index = 0) => {
  fireEvent.click((await screen.findAllByRole("button", { name: "עריכת השורה" }))[index]!);
};

// Failure scenarios deliberately retain buffers; a new test represents a fresh session.
beforeEach(() => {
  window.sessionStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DraftEditorPage", () => {
  it("focuses the requested claim after a direct clarification link loads its document", async () => {
    stubReads({});
    renderPage(true, `?claim=${encodeURIComponent(firstClaim().claim_id)}`);
    await waitFor(() => expect(document.activeElement?.id).toBe(`draft-claim-${firstClaim().claim_id}`));
  });
  it("opens in the split editing workspace with a focused preview option", async () => {
    stubReads({});

    renderPage();

    expect(await screen.findByRole("button", { name: "עריכה ותצוגה" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "תצוגה מלאה" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTitle("תצוגה מקדימה של הטיוטה")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "עריכת השורה" }).length).toBeGreaterThan(0);
  });

  it("reports a requested check in the pinned commit bar", async () => {
    stubReads({
      check: () =>
        checkResponse(HASH, false, [{ code: "MISSING_FACT", group: "facts", hard: true, message: "Missing fact" }]),
    });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "בדיקה והכנת PDF" }));

    const result = await screen.findByText("הבדיקה הושלמה ונדרשים תיקונים. הפרטים מופיעים לצד הטיוטה.");
    expect(result.closest(".sticky")).not.toBeNull();
    expect(result.closest('[role="status"]')).not.toBeNull();
  });

  it("opens explicit approval immediately after the finish check passes", async () => {
    const fetchMock = stubReads({ check: () => checkResponse(HASH, true) });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "בדיקה והכנת PDF" }));

    expect(await screen.findByRole("dialog", { name: "אישור והכנת PDF" })).toBeInTheDocument();
    expect(screen.getByText(/אני מאשר\/ת את הגרסה הזו להפקת PDF/)).toBeInTheDocument();
    /* The check is addressed to the exact document on screen, and nothing approved yet. */
    const call = fetchMock.mock.calls.find((entry) => String(entry[0]) === `${DOC_PATH}/check`);
    expect(JSON.parse(String((call?.[1] as RequestInit | undefined)?.body))).toEqual({ expected_document_hash: HASH });
    expect(fetchMock.mock.calls.some((entry) => String(entry[0]).endsWith("/approve"))).toBe(false);
  });

  it("gates AI regeneration through effective Settings without offering a silent fallback", async () => {
    stubReads({});

    renderPage(false);

    expect(await screen.findByText("יצירה מחדש באמצעות AI אינה זמינה")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "מעבר להגדרות" })).toHaveAttribute("href", "/settings");
    expect(screen.getByRole("button", { name: "יצירה מחדש של הפרק" })).toBeDisabled();
  });

  it("renders the outline the projection named, with each claim's status in Hebrew", async () => {
    stubReads({});

    renderPage();

    expect(await screen.findByText("Owned the CRM migration.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "עדכון סטטוס ומשימות" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Core Skills" })).toBeInTheDocument();
    expect(screen.getAllByText("מבוסס עובדה").length).toBeGreaterThan(0);
    /* The headline is a line of the document rather than a field: it is drawn as text
       under its own "כותרת" status. The identity card also names the target role. */
    expect(screen.getByText("כותרת", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("Account Manager", { selector: "p" })).toBeInTheDocument();
    /* The wizard's own navigation, and no trail beside it: the step back is on the bar
       that carries the step's action, and the way out is on the spine. */
    expect(screen.queryByRole("navigation", { name: "פירורי לחם" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "חזרה לניתוח והתאמה" })).toHaveAttribute("href", "/applications/app-1");
    expect(screen.getByRole("link", { name: "חזרה ללוח המועמדויות" })).toBeInTheDocument();
  });

  it("offers in-page navigation once the outline carries more than one section", async () => {
    stubReads({
      document: () =>
        jsonResponse(
          draft({
            sections: [
              { name: "Core Skills", claims: [firstClaim()] },
              { name: "Experience", claims: [] },
            ],
          }),
        ),
    });

    renderPage();

    /* Plain anchors to the section headings: a tailored CV runs long enough that reaching
       the third section meant scrolling past the first two every time. */
    const sectionNav = await screen.findByRole("navigation", { name: "מעבר לסעיפי הטיוטה" });
    expect(within(sectionNav).getByRole("link", { name: "Core Skills 1" })).toHaveAttribute("href", "#draft-section-0");
    expect(within(sectionNav).getByRole("link", { name: "Experience 0" })).toHaveAttribute("href", "#draft-section-1");
  });

  it("names the facts behind a claim by their text, never by their identifier", async () => {
    stubReads({});

    renderPage();

    expect(await screen.findByText("Owned the CRM migration end to end.")).toBeInTheDocument();
    expect(screen.queryByText(/f-1/)).not.toBeInTheDocument();
  });

  it("marks free text nothing authorized as a blocker and keeps the text", async () => {
    stubReads({
      document: () =>
        jsonResponse(
          draft({
            sections: [
              {
                name: "Core Skills",
                claims: [
                  {
                    claim_id: "c-1",
                    style: "bullet",
                    text: "Delivered 30% growth.",
                    claim_type: "pending",
                    fact_ids: [],
                    pending_reason: "no canonical fact authorizes this wording",
                  },
                ],
              },
            ],
          }),
        ),
    });

    renderPage();
    /* The unsupported line itself, after the headline and the contact: opening it shows
       the same text twice - once in the row, once copied verbatim into the fact the
       resolution flow would capture from it. */
    await editRow(2);

    expect(await screen.findAllByDisplayValue("Delivered 30% growth.")).toHaveLength(2);
    expect(screen.getByText("ללא ביסוס")).toBeInTheDocument();
    expect(screen.getByText("no canonical fact authorizes this wording")).toBeInTheDocument();
    expect(screen.getByText("הפיכת הטקסט לעובדה מאושרת")).toBeInTheDocument();
  });

  it("uses the canonical Hebrew lifecycle labels for a claim fact and its history", async () => {
    const pendingDraft = draft({
      sections: [
        {
          name: "Core Skills",
          claims: [
            {
              claim_id: "c-1",
              style: "bullet",
              text: "Delivered 30% growth.",
              claim_type: "pending",
              fact_ids: [],
              pending_reason: "הטענה עדיין אינה מבוססת.",
            },
          ],
        },
      ],
    });
    const lifecycleEvent = {
      application_id: "app-1",
      claim_id: "c-1",
      created_at: "2026-08-24T07:05:00Z",
      event_type: "fact_confirmed",
      fact_hash: "fact-hash",
      fact_id: "f-captured",
      facts_version: "facts-2",
      from_status: "pending",
      id: "event-1",
      lifecycle_version: "lifecycle-2",
      reason: "explicit confirmation",
      source: "sales.json",
      to_status: "canonical",
    };
    const fetchMock = vi.fn((input: unknown) => {
      const url = String(input);
      if (url === "/api/v1/facts/history") {
        return Promise.resolve(jsonResponse({ events: [lifecycleEvent] }));
      }
      if (url === "/api/v1/facts/f-captured") {
        return Promise.resolve(
          jsonResponse({
            events: [lifecycleEvent],
            fact: {
              confirmed_at: "2026-08-24T07:05:00Z",
              effective_dates: null,
              fact_id: "f-captured",
              link_target: null,
              meaning: "Delivered measurable growth.",
              provenance: "Candidate confirmation",
              renderings: { en: "Delivered 30% growth." },
              replaces: null,
              resume_style: "bullet",
              source: "sales.json",
              status: "canonical",
              tags: ["growth"],
            },
          }),
        );
      }
      if (url === "/api/v1/facts") {
        return Promise.resolve(jsonResponse({ items: [] }));
      }
      if (url === DOC_PATH) {
        return Promise.resolve(jsonResponse(pendingDraft));
      }
      return Promise.resolve(jsonResponse(detail()));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    expect(await screen.findByText("מצב: מקור אמת", {}, { timeout: 5_000 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "פתיחת העובדה במאגר העובדות" })).toHaveAttribute(
      "href",
      "/facts?fact=f-captured",
    );
    expect(screen.getByText("ממתינה לאישור ← מקור אמת · explicit confirmation")).toBeInTheDocument();
    expect(screen.queryByText(/\bpending\b|\bcanonical\b/)).not.toBeInTheDocument();
  }, 10_000);

  it("says how the content was built without duplicating fact lifecycle management", async () => {
    stubReads({});

    renderPage();

    const summary = (await screen.findByRole("heading", { name: "איך נבנה התוכן" })).closest("section")!;
    /* The one body line is its fact's canonical wording: counted as taken verbatim, with
       nothing reworded and nothing unsupported. */
    expect(within(summary).getByText("כלשון העובדה").nextElementSibling).toHaveTextContent("1");
    expect(within(summary).getByText("נוסח מחדש").nextElementSibling).toHaveTextContent("0");
    expect(within(summary).getByText("ללא עובדה מאחוריה").nextElementSibling).toHaveTextContent("0");
    expect(within(summary).getByText(/עובדה אחת נכנסה לקורות החיים/)).toBeInTheDocument();
    /* The summary reports the selection; changing it happens on the analysis screen. */
    expect(within(summary).getByRole("link", { name: "שינוי בחירת העובדות" })).toHaveAttribute(
      "href",
      "/applications/app-1#fact-selection",
    );
    expect(within(summary).queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "מחזור חיי העובדות" })).not.toBeInTheDocument();
    expect(screen.queryByText("יצירת עובדה ממתינה חדשה")).not.toBeInTheDocument();
  });

  it("refreshes the conflict comparison and reapplies against the current ETag", async () => {
    let documentReads = 0;
    let patchWrites = 0;
    const fetchMock = vi.fn((input: unknown, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/facts" || url === "/api/v1/facts/history") {
        return Promise.resolve(jsonResponse(url.endsWith("/history") ? { events: [] } : { items: [] }));
      }
      if (url === DOC_PATH && init?.method === "PATCH") {
        patchWrites += 1;
        return Promise.resolve(patchWrites === 1 ? conflictResponse() : updateResponse(10));
      }
      if (url === DOC_PATH) {
        documentReads += 1;
        const current =
          documentReads === 1
            ? draft()
            : draft(
                { sections: [{ name: "Core Skills", claims: [{ ...firstClaim(), text: "Saved in the other tab." }] }] },
                { document_hash: OTHER_HASH },
              );
        return Promise.resolve(jsonResponse(current, 200, documentReads === 1 ? `"${HASH}"` : `"${OTHER_HASH}"`));
      }
      return Promise.resolve(jsonResponse(detail()));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await editRow(2);
    const editor = await screen.findByDisplayValue("Owned the CRM migration.");
    fireEvent.change(editor, { target: { value: "My local wording." } });
    fireEvent.blur(editor);

    const dialog = await screen.findByRole("dialog", {
      name: "הטיוטה השתנתה בזמן העריכה",
    });
    expect(within(dialog).getByText("My local wording.")).toBeInTheDocument();
    expect(within(dialog).getByText("Saved in the other tab.")).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "החלת הטקסט שלי על הגרסה הנוכחית" }));
    await waitFor(() => expect(dialog).not.toHaveAttribute("open"));

    const patchCalls = fetchMock.mock.calls.filter(
      (call) => String(call[0]) === DOC_PATH && (call[1] as RequestInit)?.method === "PATCH",
    );
    expect(patchCalls).toHaveLength(2);
    expect(((patchCalls[0]![1] as RequestInit).headers as Headers).get("If-Match")).toBe(`"${HASH}"`);
    expect(((patchCalls[1]![1] as RequestInit).headers as Headers).get("If-Match")).toBe(`"${OTHER_HASH}"`);
  });

  it("presents the projection's own review reason rather than inventing an approval rule", async () => {
    stubReads({
      detail: () =>
        jsonResponse(
          detail({
            review_reasons: [
              {
                code: "PENDING_FACT_REQUIRES_RESOLUTION",
                message: "A claim in the active draft depends on a pending fact.",
                entity_references: {},
                allowed_resolution_actions: ["confirm_and_use_fact", "edit"],
              },
            ],
          }),
        ),
    });

    renderPage();

    expect(await screen.findByText("טענה בלי עובדה מאושרת")).toBeInTheDocument();
    // The server's English sentence is evidence, folded behind its disclosure.
    expect(screen.getByText("A claim in the active draft depends on a pending fact.")).not.toBeVisible();
    expect(screen.getByText("פרטי הסיבה")).toBeVisible();
    expect(screen.queryByRole("link", { name: "עריכת הטיוטה" })).toBeNull();
  });

  it("takes pending facts to their own row with focus", async () => {
    stubReads({
      detail: () => jsonResponse(reviewDetail()),
      document: () =>
        jsonResponse(
          draft({
            sections: [{ name: "Core Skills", claims: [{ ...firstClaim(), claim_type: "pending", fact_ids: [] }] }],
          }),
        ),
    });
    renderPage();
    expect(await screen.findByText("טענה בלי עובדה מאושרת")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "מעבר לפתרון השורה" }));
    await waitFor(() => expect(document.activeElement?.id).toBe("draft-claim-c-1"));
    expect(screen.getByText("הפיכת הטקסט לעובדה מאושרת")).toBeVisible();
  });

  it("takes a deleted dependency to its row and withholds unrelated fact confirmation", async () => {
    stubReads({
      detail: () =>
        jsonResponse(
          detail({
            review_reasons: [
              {
                code: "FACT_DELETED_REQUIRES_RESOLUTION",
                message: "A selected fact was deleted.",
                entity_references: { fact_id: "f-1" },
                allowed_resolution_actions: ["update_selection"],
              },
            ],
          }),
        ),
    });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "מעבר לשורה להסרת התלות בעובדה" }));
    await waitFor(() => expect(document.activeElement?.id).toBe("draft-claim-c-1"));
    expect(screen.queryByText("הפיכת הטקסט לעובדה מאושרת")).toBeNull();
    expect(screen.queryByRole("button", { name: "שמירת ההחלטות" })).toBeNull();
  });

  it.each(["blocked", "passed", "failed", "refresh-error", "check-error", "edit-during-confirmation"])(
    "updates document state after fact confirmation: %s",
    async (outcome) => {
      let confirmed = false;
      let retry = false;
      let checked = false;
      let version = 4;
      let wording = "Owned the CRM migration.";
      let finishConfirmation: (response: Response) => void = () => {};
      const confirmation = new Promise<Response>((resolve) => {
        finishConfirmation = resolve;
      });
      const issues =
        outcome === "failed" ? [{ code: "UNSUPPORTED", group: "facts", hard: true, message: "Still unsupported" }] : [];
      const fetchMock = vi.fn((input: unknown, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/confirm-and-use")) {
          confirmed = true;
          if (outcome === "edit-during-confirmation") return confirmation;
          return Promise.resolve(jsonResponse({ fact_id: "f-captured" }));
        }
        if (url === "/api/v1/facts/history")
          return Promise.resolve(
            jsonResponse({
              events: [{ application_id: "app-1", claim_id: "c-1", fact_id: "f-captured", event_type: "fact_created" }],
            }),
          );
        if (url === "/api/v1/facts/f-captured")
          return Promise.resolve(
            jsonResponse({
              fact: {
                fact_id: "f-captured",
                meaning: "Owned the CRM migration.",
                renderings: { en: "Owned the CRM migration." },
                resume_style: "bullet",
                status: confirmed ? "canonical" : "pending",
                tags: [],
                provenance: "Candidate",
                source: "sales.json",
              },
              events: [],
            } satisfies FactDetail),
          );
        if (url === DOC_PATH && init?.method === "PATCH") {
          version += 1;
          wording = JSON.parse(String(init.body)).claim_edits[0].text;
          return Promise.resolve(updateResponse(version));
        }
        if (url === `${DOC_PATH}/check`) {
          if (outcome === "check-error" && !retry) return Promise.resolve(jsonResponse({}, 503));
          checked = true;
          return Promise.resolve(checkResponse(hashAt(version), outcome !== "failed", issues));
        }
        if (url === DOC_PATH) {
          if (confirmed && outcome === "refresh-error" && !retry) return Promise.resolve(jsonResponse({}, 503));
          return Promise.resolve(
            jsonResponse(
              draft(
                {
                  sections: [
                    {
                      name: "Core Skills",
                      claims: [{ ...firstClaim(), claim_type: "pending", fact_ids: [], text: wording }],
                    },
                  ],
                },
                {
                  document_hash: hashAt(version),
                  content_check: checked ? (outcome === "failed" ? "failed" : "passed") : "none",
                  content_report: checked ? { passed: outcome !== "failed", groups: {}, evidence: {}, issues } : null,
                },
              ),
              200,
              `"${hashAt(version)}"`,
            ),
          );
        }
        const blocked = confirmed && outcome === "blocked";
        return Promise.resolve(
          jsonResponse(
            detail({
              application: { ...detail().application, profile: "account-manager" },
              document_hash: hashAt(version),
              available_actions: blocked ? [] : ["edit", "check"],
              review_reasons: blocked
                ? [
                    {
                      code: "FACT_DELETED_REQUIRES_RESOLUTION",
                      message: "The document depends on a fact that has been deleted.",
                      entity_references: { fact_id: "f-gone" },
                      allowed_resolution_actions: ["update_selection"],
                    },
                  ]
                : [],
            }),
          ),
        );
      });
      vi.stubGlobal("fetch", fetchMock);
      renderPage();
      fireEvent.click(await screen.findByText("הפיכת הטקסט לעובדה מאושרת"));
      fireEvent.click(await screen.findByRole("checkbox"));
      if (outcome === "edit-during-confirmation") {
        fireEvent.click(screen.getAllByRole("button", { name: "עריכת השורה" })[2]!);
        fireEvent.change(await screen.findByDisplayValue(wording), { target: { value: "Saved before confirmation." } });
      }
      fireEvent.click(screen.getByRole("button", { name: "אישור העובדה ושימוש בה" }));
      if (outcome === "edit-during-confirmation") {
        await waitFor(() => expect(confirmed).toBe(true));
        expect(version).toBe(5);
        fireEvent.change(screen.getByRole("textbox", { name: "טקסט השורה" }), {
          target: { value: "Edited during confirmation." },
        });
        await act(async () => finishConfirmation(jsonResponse({ fact_id: "f-captured" })));
      }
      expect(await screen.findByText("העובדה אושרה ונבחרה")).toBeInTheDocument();
      if (outcome.endsWith("error")) {
        const retryButton = await screen.findByRole("button", { name: "ניסיון נוסף לעדכון מצב הטיוטה" });
        expect(screen.getByRole("button", { name: "בדיקה והכנת PDF" })).toBeDisabled();
        retry = true;
        fireEvent.click(retryButton);
        await waitFor(() => expect(screen.queryByRole("button", { name: "ניסיון נוסף לעדכון מצב הטיוטה" })).toBeNull());
      }
      if (outcome === "blocked") {
        /* The projection no longer offers the check, so none is sent: the blocker is the
           answer, reported where the editor reports blockers. */
        expect(await screen.findByText("יש לשנות את בחירת העובדות של המסמך במסך ההכנה.")).toBeInTheDocument();
        expect(fetchMock.mock.calls.some((call) => String(call[0]) === `${DOC_PATH}/check`)).toBe(false);
        expect(screen.getByRole("button", { name: "בדיקה והכנת PDF" })).toBeDisabled();
      } else {
        await screen.findByRole("heading", {
          name: outcome === "failed" ? "נדרשים תיקונים בקובץ" : "הקובץ עבר בדיקה",
        });
        const request = fetchMock.mock.calls.find((call) => String(call[0]) === `${DOC_PATH}/check`);
        expect(JSON.parse(String(request![1]!.body))).toEqual({
          expected_document_hash: hashAt(outcome === "edit-during-confirmation" ? 6 : 4),
        });
        if (outcome === "edit-during-confirmation")
          expect(screen.getByDisplayValue("Edited during confirmation.")).toBeInTheDocument();
        if (outcome === "failed") expect(screen.getByText("Still unsupported")).toBeInTheDocument();
      }
      // Confirmation alone never relinks or authorizes this pending claim.
      expect(screen.getByText("ללא ביסוס")).toBeInTheDocument();
      expect(fetchMock.mock.calls.filter((call) => String(call[0]).endsWith("/confirm-and-use"))).toHaveLength(1);
      expect(
        fetchMock.mock.calls.some(
          (call) => String(call[0]).endsWith("/approve") || String(call[0]).endsWith("/document/draft"),
        ),
      ).toBe(false);
      expect(screen.queryByRole("dialog", { name: "אישור והכנת PDF" })).toBeNull();
    },
  );

  it.each(["conflict", "failure"])("preserves local text and stops navigation after a save %s", async (outcome) => {
    const fetchMock = vi.fn((input: unknown, init?: RequestInit) => {
      const url = String(input);
      if (url === DOC_PATH && init?.method === "PATCH")
        return Promise.resolve(outcome === "conflict" ? conflictResponse() : jsonResponse({}, 503));
      if (url === DOC_PATH) return Promise.resolve(jsonResponse(draft()));
      if (url === "/api/v1/facts/history") return Promise.resolve(jsonResponse({ events: [] }));
      return Promise.resolve(jsonResponse(detail()));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderPage();
    await editRow(2);
    fireEvent.change(await screen.findByDisplayValue("Owned the CRM migration."), {
      target: { value: "Keep my text." },
    });
    fireEvent.click(screen.getByRole("link", { name: "חזרה לניתוח והתאמה" }));
    expect(await screen.findByText("לא ניתן להמשיך לפני שמירת העריכות")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "הכנת קורות החיים" })).toBeNull();
    expect(screen.getByDisplayValue("Keep my text.")).toBeInTheDocument();
    if (outcome === "conflict") {
      // The refusal announcement and native showModal effect can settle separately.
      const dialog = await screen.findByRole("dialog", { name: "הטיוטה השתנתה בזמן העריכה" });
      expect(dialog).toBeVisible();
      expect(within(dialog).getByText("Keep my text.")).toBeInTheDocument();
    }
  });

  it("says plainly when there is no document to read yet, and reads nothing", async () => {
    const fetchMock = stubReads({
      detail: () =>
        jsonResponse(
          detail({
            document_id: null,
            document_hash: null,
            document_analysis_id: null,
            preparation_state: "needs_analysis",
          }),
        ),
    });

    renderPage();

    expect(await screen.findByText("לקורות החיים של המועמדות הזו אין עדיין טיוטה")).toBeInTheDocument();
    expect(fetchMock.mock.calls.every((call) => !String(call[0]).startsWith(DOC_PATH))).toBe(true);
  });

  it("points a document without content back to where it is generated", async () => {
    stubReads({
      detail: () => jsonResponse(detail({ preparation_state: "ready_to_draft" })),
      document: () =>
        jsonResponse(cvDocument({ content: null, outline: null, content_check: "none", content_report: null })),
    });

    renderPage();

    expect(await screen.findByText("לקורות החיים של המועמדות הזו אין עדיין טיוטה")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "עריכת השורה" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "בדיקה והכנת PDF" })).not.toBeInTheDocument();
  });

  /* Approval is a state of the one document, not a record that replaces it: the editor
     stays open beside the render step, and editing simply returns the document to draft. */
  it("keeps the approved document editable beside its render step", async () => {
    const fetchMock = stubReads({
      detail: () => jsonResponse(detail({ preparation_state: "approved", content_check: "passed" })),
      document: () => jsonResponse(draft({}, { preparation_state: "approved", content_check: "passed" })),
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: "הגרסה אושרה" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "יצירת HTML ו־PDF" })).toBeEnabled());
    for (const button of await screen.findAllByRole("button", { name: "עריכת השורה" })) expect(button).toBeEnabled();
    /* A visit to an approved document queues nothing by itself, and the finish action it
       already passed is not offered a second time. */
    expect(fetchMock.mock.calls.some((call) => String(call[0]).endsWith("/render"))).toBe(false);
    expect(screen.queryByRole("button", { name: "בדיקה והכנת PDF" })).not.toBeInTheDocument();
  });

  /* The render is the step's own last act, so it is reported in the step, once. It used to
     be a banner of the render panel's beside a corner panel of the overlay's, both
     spinning over the same run. */
  it("reports a running render once, in the step, rather than as a banner and a corner panel", async () => {
    const renderRun = {
      id: "op-render",
      application_id: "app-1",
      operation_type: "render_document",
      status: "running",
      is_terminal: false,
      phase: "executing",
      message: "",
      created_at: "2026-08-24T07:00:00Z",
      outputs: [],
      available_actions: ["cancel"],
    };
    stubReads({
      detail: () => jsonResponse(detail({ preparation_state: "approved", content_check: "passed" })),
      document: () => jsonResponse(draft({}, { preparation_state: "approved", content_check: "passed" })),
      render: () =>
        new Response(JSON.stringify({ ...renderRun, status: "queued", phase: "queued" }), {
          status: 202,
          headers: { "Content-Type": "application/json", Location: "/api/v1/operations/op-render" },
        }),
      operation: () => jsonResponse(renderRun),
    });

    renderPage();
    const start = await screen.findByRole("button", { name: "יצירת HTML ו־PDF" });
    await waitFor(() => expect(start).toBeEnabled());
    fireEvent.click(start);

    const report = await screen.findByRole("region", { name: "הרצת יצירת קובץ קורות החיים" });
    expect(report).not.toHaveClass("fixed");
    expect(report).toHaveTextContent("המסך יעבור לקורות החיים המוכנים למסירה");
    expect(screen.queryByRole("heading", { name: "הגרסה אושרה" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: "הרצת יצירת קובץ קורות החיים" })).toHaveLength(1);
  });

  it("reports the last failed render on the approved document and keeps it editable", async () => {
    stubReads({
      detail: () =>
        jsonResponse(
          detail({
            preparation_state: "approved",
            content_check: "passed",
            last_render_error: {
              code: "pdf_page_limit",
              pages: 2,
              maximum: 1,
              failure_code: "RENDER_FAILED",
              detail: "Rendered PDF has 2 pages; maximum 1.",
            },
          }),
        ),
      document: () => jsonResponse(draft({}, { preparation_state: "approved", content_check: "passed" })),
    });

    renderPage();

    expect(await screen.findByText("יצירת הקובץ האחרונה נכשלה")).toBeInTheDocument();
    expect(screen.getByText(/קובץ ה־PDF כולל 2 עמודים, אך הפרופיל מאפשר לכל היותר 1/)).toBeInTheDocument();
    expect(screen.queryByText("Rendered PDF has 2 pages; maximum 1.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "יצירת HTML ו־PDF" })).toBeInTheDocument();
    for (const button of await screen.findAllByRole("button", { name: "עריכת השורה" })) expect(button).toBeEnabled();
  });

  it("states why a structural line stays instead of offering a removal that would be refused", async () => {
    stubReads({});

    renderPage();

    expect(await screen.findByText("שורת הכותרת היא חלק ממבנה המסמך ואינה נמחקת.")).toBeInTheDocument();
  });
});

describe("DraftEditorPage selection changes", () => {
  /* The document as it stands after one earlier pin: the fact accounting shows it, and
     the selection overlay records it - the overlay is what a new decision is added to. */
  const omittedDraft = (): CVDocument =>
    draft(
      {},
      {
        selection: { ...cvDocument().selection, pinned_fact_ids: ["f-pinned"] },
        facts: [
          ...baseFacts(),
          {
            fact_id: "f-pinned",
            text: "Built the reporting pipeline.",
            linked_claim_ids: ["c-9"],
            section: "Core Skills",
            outcome: "pinned",
            reason: null,
          },
          {
            fact_id: "f-out",
            text: "Ran the partner onboarding programme.",
            linked_claim_ids: [],
            section: "Core Skills",
            outcome: "omitted",
            reason: "below_section_budget",
          },
        ],
      },
    );

  /* Removing a fact-backed line is the editor's one selection change: it excludes the
     facts behind the line once the undo window closes. The caller owns the fake clock,
     installed before render (see the removal tests below). */
  const removeFirstLine = async () => {
    fireEvent.click((await screen.findAllByRole("button", { name: "הסרת השורה" }))[0]!);
    const dialog = await screen.findByRole("dialog", { name: "הסרת השורה?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "אישור ההסרה" }));
    await vi.advanceTimersByTimeAsync(6000);
  };

  it("refuses a selection change when saving local wording failed", async () => {
    const fetchMock = vi.fn((input: unknown, init?: RequestInit) => {
      const url = String(input);
      if (url === DOC_PATH && init?.method === "PATCH") return Promise.resolve(jsonResponse({}, 503));
      if (url === DOC_PATH) return Promise.resolve(jsonResponse(omittedDraft()));
      if (url === "/api/v1/facts/history") return Promise.resolve(jsonResponse({ events: [] }));
      return Promise.resolve(jsonResponse(detail()));
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      renderPage();
      await editRow(2);
      fireEvent.change(await screen.findByDisplayValue("Owned the CRM migration."), {
        target: { value: "Keep before selection." },
      });
      await removeFirstLine();
      await screen.findByText("בחירת העובדות לא שונתה");
      /* Opening the removal closes the edit field; the unsaved wording stays on the line. */
      expect(screen.getAllByText("Keep before selection.").length).toBeGreaterThan(0);
      expect(fetchMock.mock.calls.some((call) => String(call[0]) === `${DOC_PATH}/selection`)).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("asks for confirmation before removing a line, then stages it behind an undo window", async () => {
    const fetchMock = stubReads({ document: () => jsonResponse(omittedDraft()) });
    /* The undo timer is created by the confirmation click, so the fake clock must own
       timers before that click (and before render). Switching clocks after staging leaves
       the real timeout behind, where advancing the fake clock cannot settle it. */
    vi.useFakeTimers({ shouldAdvanceTime: true });

    try {
      renderPage();
      fireEvent.click(await screen.findByRole("button", { name: "הסרת השורה" }));

      /* A single click on the trash icon must not fire the removal by itself. */
      const dialog = await screen.findByRole("dialog", { name: "הסרת השורה?" });
      expect(fetchMock.mock.calls.some((call) => String(call[0]) === `${DOC_PATH}/selection`)).toBe(false);

      fireEvent.click(within(dialog).getByRole("button", { name: "אישור ההסרה" }));

      /* Confirming stages the removal instead of sending it straight away, offering an undo. */
      expect(await screen.findByRole("button", { name: "ביטול ההסרה" })).toBeVisible();
      expect(fetchMock.mock.calls.some((call) => String(call[0]) === `${DOC_PATH}/selection`)).toBe(false);

      await vi.advanceTimersByTimeAsync(6000);

      await waitFor(() =>
        expect(fetchMock.mock.calls.some((call) => String(call[0]) === `${DOC_PATH}/selection`)).toBe(true),
      );
      const call = fetchMock.mock.calls.find((entry) => String(entry[0]) === `${DOC_PATH}/selection`);
      expect(JSON.parse(String((call?.[1] as RequestInit | undefined)?.body)).excluded_fact_ids).toEqual(["f-1"]);
      expect(fetchMock.mock.calls.some((entry) => (entry[1] as RequestInit)?.method === "PATCH")).toBe(false);
    } finally {
      vi.useRealTimers();
    }
  });

  it("cancels a staged removal with the undo action, never sending the exclusion", async () => {
    const fetchMock = stubReads({ document: () => jsonResponse(omittedDraft()) });

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "הסרת השורה" }));
    const dialog = await screen.findByRole("dialog", { name: "הסרת השורה?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "אישור ההסרה" }));

    fireEvent.click(await screen.findByRole("button", { name: "ביטול ההסרה" }));

    await waitFor(() => expect(screen.queryByRole("button", { name: "ביטול ההסרה" })).not.toBeInTheDocument());
    expect(fetchMock.mock.calls.some((call) => String(call[0]) === `${DOC_PATH}/selection`)).toBe(false);
  });

  it("presents the manual-wording refusal in Hebrew, keeping the backend's detail out of the page", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    stubReads({
      document: () => jsonResponse(omittedDraft()),
      selection: () =>
        jsonResponse(
          {
            type: "about:blank#regeneration_required",
            title: "Precondition Failed",
            status: 412,
            code: "REGENERATION_REQUIRED",
            detail: "the document carries wording a deterministic rebuild would discard",
          },
          412,
        ),
    });

    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      renderPage();
      await removeFirstLine();

      expect(await screen.findByText("בחירת העובדות לא שונתה")).toBeInTheDocument();
      expect(screen.getByText(/המסמך כולל ניסוח ידני שבנייה מחדש הייתה מוחקת/)).toBeInTheDocument();
      expect(screen.queryByText(/deterministic rebuild/)).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("DraftEditorPage regeneration", () => {
  const accepted = (): Response =>
    new Response(
      JSON.stringify({
        id: "op-7",
        application_id: "app-1",
        operation_type: "regenerate_claim",
        status: "queued",
        is_terminal: false,
        phase: "queued",
        message: "",
        created_at: "2026-08-24T07:00:00Z",
        outputs: [],
        available_actions: ["cancel"],
      }),
      {
        status: 202,
        headers: { "Content-Type": "application/json", Location: "/api/v1/operations/op-7" },
      },
    );

  /* The regeneration is reported in place. It used to navigate to the Operation's own
     route, which took the draft off the screen at the moment the user was waiting to see
     what became of one of its lines - and the way back from there led to the Application
     screen rather than to the editor they had left. The overlay that opens here is the
     same one the Application screen uses. */
  it("freezes the exact saved version and reports the queued Operation in place", async () => {
    const fetchMock = stubReads({ regenerate: () => accepted() });

    renderPage();
    const regenerate = await screen.findByRole("button", { name: "יצירה מחדש של השורה" });
    const identity = screen.getByRole("heading", { name: "כותרת ופרטי קשר" }).closest("section")!;
    expect(within(identity).queryByRole("button", { name: "יצירה מחדש של השורה" })).not.toBeInTheDocument();
    expect(within(identity).getAllByRole("button", { name: "עריכת השורה" })).toHaveLength(2);
    fireEvent.click(regenerate);

    /* The overlay, not the route: the editor's own heading is still on screen under it. */
    expect(await screen.findByRole("heading", { name: "הרצת יצירה מחדש של טענה" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "טיוטה ואימות" })).toBeInTheDocument();
    const call = fetchMock.mock.calls.find((entry) => String(entry[0]).endsWith("/regenerate-claim"));
    /* The document's hash is its whole identity: a save landing mid flight changes it, so
       activation discards the result instead of overwriting the user's edit. */
    expect(String(call?.[0])).toBe(`${DOC_PATH}/regenerate-claim`);
    expect(JSON.parse(String((call?.[1] as RequestInit | undefined)?.body))).toEqual({
      expected_document_hash: HASH,
      claim_id: "c-1",
      keep_text: false,
    });
    expect(((call?.[1] as RequestInit | undefined)?.headers as Headers | undefined)?.get("Idempotency-Key")).toBe(
      `${HASH}:c-1`,
    );

    /* Hiding the run does not make the draft safe to change: every edit would be addressed
       to the version the regeneration is replacing, so the commands wait for it. */
    fireEvent.click(screen.getByRole("button", { name: "סגירה" }));
    expect(screen.getByRole("button", { name: /פירוט ההרצה/ })).toBeInTheDocument();
    for (const button of screen.getAllByRole("button", { name: "עריכת השורה" })) expect(button).toBeDisabled();
    for (const button of screen.getAllByRole("button", { name: "יצירה מחדש של השורה" })) expect(button).toBeDisabled();
  });

  it("reads the document back when regeneration activates its output", async () => {
    let documentReads = 0;
    let finishOperation!: (response: Response) => void;
    const operationReply = new Promise<Response>((resolve) => {
      finishOperation = resolve;
    });
    const completed: Operation = {
      id: "op-complete",
      application_id: "app-1",
      operation_type: "regenerate_claim",
      status: "succeeded",
      phase: "completed",
      is_terminal: true,
      available_actions: [],
      outputs: [],
      message: "",
      created_at: "2026-08-24T07:00:00Z",
    };
    const running: Operation = { ...completed, status: "running", phase: "executing", is_terminal: false };
    stubReads({
      detail: () =>
        jsonResponse(
          detail({
            latest_operation: running,
          }),
        ),
      operation: () => operationReply,
      document: () => {
        documentReads += 1;
        return jsonResponse(draft());
      },
    });

    renderPage();

    await screen.findByText("Owned the CRM migration.");
    finishOperation(jsonResponse(completed));
    await waitFor(() => expect(documentReads).toBeGreaterThanOrEqual(2));
  });

  it("withholds regeneration while an edit is still unsaved, and says why", async () => {
    stubReads({});

    renderPage();
    await editRow();
    const editors = await screen.findAllByLabelText("טקסט השורה");
    fireEvent.change(editors[0]!, { target: { value: "typed but not saved" } });

    expect(
      await screen.findByText("יצירה מחדש מוקפאת על הגרסה השמורה של הטיוטה, ולכן היא זמינה רק אחרי שהשמירה הסתיימה."),
    ).toBeInTheDocument();
    for (const button of screen.getAllByRole("button", { name: "יצירה מחדש של השורה" })) {
      expect(button).toBeDisabled();
    }
  });
});

describe("DraftEditorPage preview", () => {
  it("frames the server-rendered draft in an isolated sandbox, marked as a draft", async () => {
    stubReads({});

    renderPage();

    const frame = await screen.findByTitle("תצוגה מקדימה של הטיוטה");
    expect(frame).toHaveAttribute("src", `${DOC_PATH}/preview?v=${HASH}`);
    /* An empty sandbox is the point: no allow-same-origin and no allow-scripts, so the
       document renders in an opaque origin and cannot reach this page. */
    expect(frame).toHaveAttribute("sandbox", "");
    expect(
      within(screen.getByRole("heading", { name: "תצוגה מקדימה" }).closest("section")!).getByText("טיוטה"),
    ).toBeInTheDocument();
  });

  it("offers the draft's own PDF in a new tab, before any approval", async () => {
    stubReads({});

    renderPage();

    const link = await screen.findByRole("link", { name: "PDF הטיוטה" });
    expect(link).toHaveAttribute("href", `${DOC_PATH}/preview.pdf?v=${HASH}`);
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("opens on the draft as text, with the fact behind each line one disclosure away", async () => {
    stubReads({});

    renderPage();

    expect(await screen.findByText("Owned the CRM migration.")).toBeInTheDocument();
    /* No field until a line is opened: this is a page to read and sign, and the pencil is
       what turns one line into a field. The fact a line was built from is folded under
       it, so sixty lines do not print sixty evidence lists, and opening it shows the
       fact beside the wording the CV uses. */
    expect(screen.queryByLabelText("טקסט השורה")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "עריכת השורה" }).length).toBeGreaterThan(0);
    const row = document.getElementById("draft-claim-c-1")!;
    expect(within(row).getByText("המקור: עובדה אחת")).toBeVisible();
    expect(within(row).getByText("Owned the CRM migration end to end.")).not.toBeVisible();
    expect(screen.getByTitle("תצוגה מקדימה של הטיוטה")).toBeInTheDocument();
    /* The single finish action is pinned rather than left at the foot of a column. It
       starts with the check and changes to explicit approval only after that passes. */
    expect(screen.getByRole("button", { name: "בדיקה והכנת PDF" })).toBeEnabled();
    expect(
      screen.getByText("זה הצעד הסופי: בדיקה ואז אישור שמכין את ה־PDF. כדי רק לראות PDF, פתחו את PDF הטיוטה."),
    ).toBeInTheDocument();
  });

  it("keeps an outdated report on screen, marked as such, with the check still offered", async () => {
    stubReads({
      detail: () => jsonResponse(detail({ content_check: "outdated" })),
      document: () =>
        jsonResponse(
          draft(
            {},
            {
              content_check: "outdated",
              content_report: {
                passed: true,
                groups: {},
                evidence: {},
                issues: [{ code: "SOFT", group: "copy", hard: false, message: "Earlier warning" }],
              },
            },
          ),
        ),
    });

    renderPage();

    expect(await screen.findByRole("button", { name: "בדיקה והכנת PDF" })).toBeEnabled();
    expect(screen.getByText("תוצאת הבדיקה אינה מעודכנת")).toBeInTheDocument();
    expect(
      within(screen.getByRole("heading", { name: "בדיקת הקובץ" }).closest("section")!).getByText("Earlier warning"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("זה הצעד הסופי: בדיקה ואז אישור שמכין את ה־PDF. כדי רק לראות PDF, פתחו את PDF הטיוטה."),
    ).toBeVisible();
  });

  it("shows the text just typed when the line is closed, not the version on the server", async () => {
    stubReads({});

    renderPage();
    await editRow();
    const editors = await screen.findAllByLabelText("טקסט השורה");
    fireEvent.change(editors[0]!, { target: { value: "typed then closed" } });

    fireEvent.click(screen.getAllByRole("button", { name: "סיום עריכת השורה" })[0]!);

    expect(screen.getByText("typed then closed")).toBeInTheDocument();
    expect(screen.queryByLabelText("טקסט השורה")).not.toBeInTheDocument();
  });
});
