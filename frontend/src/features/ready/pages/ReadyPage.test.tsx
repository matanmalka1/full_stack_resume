import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail } from "@/api/contracts";
import { HASH, cvDocument, detail, json, renderRoute } from "@/test/fixtures";
import { ReadyPage } from "./ReadyPage";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const readyDetail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  detail({
    preparation_state: "ready",
    document_state: "ready",
    approved_at: "2026-08-25T08:00:00Z",
    available_actions: ["edit", "submit", "download_pdf"],
    recommended_action: "submit",
    ...overrides,
  });

/* One answer per resource the screen reads, and the submission it records. */
const stubReads = (projection: ApplicationDetail) => {
  const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    if (init?.method === "POST" && url.endsWith("/submissions")) {
      return Promise.resolve(
        json(
          {
            application_id: "app-1",
            submission_id: "submission-1",
            current_status: "applied",
            document_hash: HASH,
            warnings: [],
          },
          201,
        ),
      );
    }
    if (url.endsWith("/document/decision-markdown")) {
      return Promise.resolve(json({ application_id: "app-1", document_id: "doc-1", markdown: "# Decision" }));
    }
    if (url.endsWith("/document")) {
      return Promise.resolve(
        json(cvDocument({ document_state: projection.document_state, approved_at: projection.approved_at })),
      );
    }
    return Promise.resolve(json(projection));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
};

const renderReady = () => renderRoute("/applications/app-1/ready", "/applications/:applicationId/ready", <ReadyPage />);

describe("ReadyPage", () => {
  it("offers the Ready document's PDF and the way back to editing it", async () => {
    stubReads(readyDetail());
    renderReady();

    expect(await screen.findByRole("heading", { name: "מוכן למסירה" })).toBeInTheDocument();
    for (const link of await screen.findAllByRole("link", { name: "הורדת PDF" })) {
      expect(link).toHaveAttribute("href", `/api/v1/applications/app-1/document/pdf?v=${HASH}`);
    }
    /* Editing a Ready document is allowed; it is the way back, not a new record. */
    expect(screen.getByRole("link", { name: "חזרה לעריכת הטיוטה" })).toHaveAttribute(
      "href",
      "/applications/app-1/draft",
    );
    const technicalDetails = screen.getByText("פרטים טכניים");
    expect(screen.getByText(HASH)).not.toBeVisible();
    fireEvent.click(technicalDetails);
    expect(screen.getByText(HASH)).toBeVisible();
  });

  it("records a submission against the exact Ready document hash", async () => {
    const fetchMock = stubReads(readyDetail());
    renderReady();

    fireEvent.click(await screen.findByRole("button", { name: "רישום ההגשה" }));
    fireEvent.click(screen.getByRole("button", { name: "אישור ורישום ההגשה" }));

    await screen.findByText("ההגשה נרשמה");
    expect(screen.getByRole("link", { name: "סיום וחזרה ללוח" })).toHaveAttribute("href", "/");
    const request = fetchMock.mock.calls.find(
      (call) => call[1]?.method === "POST" && String(call[0]).endsWith("/submissions"),
    );
    expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({
      expected_document_hash: HASH,
      metadata: {},
    });
  });

  it("names a document already on record as submitted and asks before recording a second one", async () => {
    stubReads(
      readyDetail({
        recruitment_timeline: [
          {
            id: "event-1",
            item_type: "submission",
            submission_type: "internal",
            document_hash: HASH,
            occurred_at: "2026-08-25T09:00:00Z",
            actor_type: "user",
            client: "web",
            from_status: "saved",
            to_status: "applied",
            reason: "submission recorded",
            metadata: {},
          },
        ],
      }),
    );
    renderReady();

    const aside = await screen.findByRole("complementary", { name: "פרטי המסמך והבדיקה" });
    fireEvent.click(await within(aside).findByText("אפשרויות נוספות"));
    fireEvent.click(await screen.findByRole("button", { name: "רישום הגשה נוספת" }));
    expect(await screen.findByText("קורות החיים האלה כבר נרשמו כמוגשים")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "אישור ורישום ההגשה" })).toBeDisabled();

    fireEvent.click(screen.getByLabelText("אני מבקש לרשום הגשה נוספת של אותם קורות חיים"));
    expect(screen.getByRole("button", { name: "אישור ורישום ההגשה" })).toBeEnabled();
  });

  it("sends a document that changed since rendering back to the editor, offering nothing to send", async () => {
    stubReads(
      readyDetail({ document_state: "draft", preparation_state: "draft_in_progress", available_actions: ["edit"] }),
    );
    renderReady();

    expect(await screen.findByRole("heading", { name: "קורות החיים אינם מוכנים כרגע" })).toBeInTheDocument();
    expect(screen.getByText("המסמך השתנה מאז שהופק")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "מעבר לעורך הטיוטה" })).toHaveAttribute(
      "href",
      "/applications/app-1/draft",
    );
    expect(screen.queryByRole("link", { name: "הורדת PDF" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "רישום ההגשה" })).not.toBeInTheDocument();
  });
});
