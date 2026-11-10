import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Fact } from "@/api/contracts";
import { json, renderRoute } from "@/test/fixtures";
import { FactsPage } from "./FactsPage";

const fact = (overrides: Partial<Fact> = {}): Fact => ({
  fact_id: "fact.backend",
  meaning: "Built backend services",
  renderings: { en: "Built backend services", he: "בניית שירותי Backend" },
  resume_style: "bullet",
  source: "development.json",
  status: "canonical",
  tags: ["backend", "api"],
  ...overrides,
});
const event = (item: Fact) => ({
  id: `event-${item.fact_id}`,
  fact_id: item.fact_id,
  source: item.source,
  event_type: "fact_created",
  from_status: null,
  to_status: item.status,
  application_id: null,
  claim_id: null,
  reason: "candidate confirmation",
  fact_hash: "hash",
  facts_version: "facts-1",
  lifecycle_version: "lifecycle-1",
  created_at: "2026-09-10T08:00:00Z",
});

const targets = (attached = false) => ({
  profiles: [
    {
      profile: "development",
      label: "Software Engineer",
      sections: [{ section: "Experience", label: "ניסיון מקצועי", attached, pinned: false }],
    },
  ],
});

/* Answers the pool and each fact's detail from one list, the way the API does. */
const stubFacts = (items: Fact[], recorded: (item: Fact) => string | null = (item) => item.status) =>
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string | URL | Request) => {
      const url = String(input);
      if (url === "/api/v1/facts")
        return Promise.resolve(json({ items: items.map((item) => ({ fact: item, recorded_status: recorded(item) })) }));
      if (url.includes("/attachment-targets")) return Promise.resolve(json(targets()));
      const item = items.find((candidate) => url.endsWith(`/${candidate.fact_id}`));
      if (item !== undefined) return Promise.resolve(json({ fact: item, events: [event(item)] }));
      return Promise.resolve(json({}, 404));
    }),
  );

const sales = fact({
  fact_id: "fact.sales",
  meaning: "Managed accounts",
  renderings: { en: "Managed accounts" },
  source: "sales.json",
  status: "pending",
  tags: ["sales"],
});

afterEach(() => vi.unstubAllGlobals());

describe("FactsPage", () => {
  it("shows a reconciliation blocker when the store and lifecycle trail disagree", async () => {
    stubFacts([fact()], () => "pending");

    renderRoute("/facts?fact=fact.backend", "/facts", <FactsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("נמצאה אי־התאמה ביומן העובדות");
    await screen.findByRole("heading", { level: 1, name: "בניית שירותי Backend" });
    expect(screen.queryByRole("button", { name: "צירוף העובדה לסעיף" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "יצירת תיקון לעובדה" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "אפשרויות נוספות" })).not.toBeInTheDocument();
  });

  it("offers no new fact while the trail is out of sync", async () => {
    stubFacts([fact()], () => "pending");

    renderRoute("/facts", "/facts", <FactsPage />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "עובדה חדשה" })).not.toBeInTheDocument();
  });

  it("shows a load failure without presenting an empty pool", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(json({ detail: "failed" }, 500))),
    );
    renderRoute("/facts", "/facts", <FactsPage />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText("לא נמצאו עובדות התואמות לחיפוש.")).not.toBeInTheDocument();
  });

  /* A section per knowledge file, a block per kind inside it, a fact per row; each fact
     links to its own page. */
  it("lists the pool and narrows it by search and by knowledge file", async () => {
    stubFacts([fact(), sales]);

    renderRoute("/facts", "/facts", <FactsPage />);
    const table = await screen.findByRole("region", { name: "רשימת העובדות" });
    expect(within(table).getByRole("link", { name: "בניית שירותי Backend" })).toHaveAttribute(
      "href",
      "/facts?fact=fact.backend",
    );
    expect(within(table).getByRole("link", { name: "Managed accounts" })).toBeInTheDocument();
    /* Each knowledge file is its own section, and its facts sit under their kind. */
    const development = within(table).getByRole("region", { name: "ניסיון בפיתוח" });
    expect(within(development).getByRole("heading", { level: 3, name: "שורות ניסיון 1" })).toBeInTheDocument();
    /* A wide screen's outline jumps to each file. */
    expect(
      within(screen.getByRole("navigation", { name: "תוכן המאגר" })).getByRole("link", { name: "ניסיון בפיתוח 1" }),
    ).toHaveAttribute("href", "#fact-file-development-json");

    fireEvent.change(screen.getByLabelText("חיפוש עובדות"), { target: { value: "managed" } });
    expect(within(table).queryByRole("link", { name: "בניית שירותי Backend" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("חיפוש עובדות"), { target: { value: "" } });

    fireEvent.click(screen.getByRole("button", { name: "ניסיון במכירות 1" }));
    expect(within(table).getByRole("link", { name: "Managed accounts" })).toBeInTheDocument();
    expect(within(table).queryByRole("link", { name: "בניית שירותי Backend" })).not.toBeInTheDocument();
  });

  it("leads from the pending banner to the one fact that waits", async () => {
    stubFacts([fact(), sales]);

    renderRoute("/facts", "/facts", <FactsPage />);
    expect(await screen.findByRole("link", { name: /עובדה אחת ממתינה לאישורך/ })).toHaveAttribute(
      "href",
      "/facts?fact=fact.sales",
    );
  });

  it("narrows the pool to the facts that wait when several do", async () => {
    stubFacts([fact(), sales, fact({ fact_id: "fact.other", renderings: { en: "Other" }, status: "pending" })]);

    renderRoute("/facts", "/facts", <FactsPage />);
    const banner = await screen.findByRole("button", { name: /2 עובדות ממתינות לאישורך/ });
    const table = screen.getByRole("region", { name: "רשימת העובדות" });
    fireEvent.click(banner);
    expect(banner).toHaveAttribute("aria-pressed", "true");
    expect(within(table).queryByRole("link", { name: "בניית שירותי Backend" })).not.toBeInTheDocument();
    fireEvent.click(banner);
    expect(within(table).getByRole("link", { name: "בניית שירותי Backend" })).toBeInTheDocument();
  });

  it("opens a fact as its own page and marks the exact history event from a deep link", async () => {
    stubFacts([fact()]);

    renderRoute("/facts?fact=fact.backend&event=event-fact.backend", "/facts", <FactsPage />);

    expect(await screen.findByRole("heading", { level: 1, name: "בניית שירותי Backend" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "חזרה למאגר העובדות" })).toHaveAttribute("href", "/facts");
    expect(screen.getByRole("heading", { name: "ניסוח באנגלית" })).toBeInTheDocument();
    expect(
      within(screen.getByRole("complementary", { name: "פרטי העובדה" })).getByText("ניסיון בפיתוח"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "רשימת העובדות" })).not.toBeInTheDocument();
    expect(screen.getByText(/נוצרה כממתינה/).closest("li")).toHaveAttribute("aria-current", "location");
  });

  it("uses explicit replacement and attachment commands", async () => {
    let current = fact();
    const requests: Array<{ body: unknown; method: string; url: string }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (method !== "GET")
          requests.push({ body: init?.body === undefined ? undefined : JSON.parse(String(init.body)), method, url });
        if (url === "/api/v1/facts" && method === "GET")
          return Promise.resolve(json({ items: [{ fact: current, recorded_status: current.status }] }));
        if (url === "/api/v1/facts" && method === "POST") {
          current = fact({ fact_id: "fact.correction", replaces: "fact.backend", status: "pending" });
          return Promise.resolve(
            json(
              {
                fact: current,
                event_id: "event-correction",
                facts_version: "facts-1",
                lifecycle_version: "lifecycle-2",
              },
              201,
            ),
          );
        }
        if (url.includes("/attachment-targets")) return Promise.resolve(json(targets()));
        if (url.endsWith("/attachments") && method === "POST")
          return Promise.resolve(
            json(
              {
                fact: current,
                event_id: "event-attach",
                facts_version: "facts-2",
                lifecycle_version: "lifecycle-2",
                profile: "development",
                section: "Experience",
                pinned: false,
                profile_store_version: "profiles-2",
              },
              201,
            ),
          );
        if (url.endsWith("/fact.backend")) return Promise.resolve(json({ fact: current, events: [event(current)] }));
        return Promise.resolve(json({}, 404));
      }),
    );

    renderRoute("/facts?fact=fact.backend", "/facts", <FactsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "צירוף העובדה לסעיף" }));
    await waitFor(() => expect(requests.some((request) => request.url.endsWith("/attachments"))).toBe(true));
    expect(requests.find((request) => request.url.endsWith("/attachments"))?.body).toEqual({
      pin: false,
      profile: "development",
      section: "Experience",
    });

    fireEvent.click(screen.getByRole("button", { name: "יצירת תיקון לעובדה" }));
    fireEvent.click(screen.getByRole("button", { name: "יצירת עובדת תיקון ממתינה" }));
    await waitFor(() => expect(requests.some((request) => request.url === "/api/v1/facts")).toBe(true));
    const correction = requests.find((request) => request.url === "/api/v1/facts");
    expect(correction?.body).toMatchObject({
      replaces: "fact.backend",
      reason: "canonical correction created from the candidate facts page",
    });
  });

  it("asks before promoting a pending fact to the source of truth", async () => {
    const item = fact({ status: "pending" });
    const requests: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        if (init?.method === "POST") {
          requests.push(url);
          const next = fact({ status: "canonical" });
          return Promise.resolve(
            json({ fact: next, event_id: "event-next", facts_version: "facts-2", lifecycle_version: "lifecycle-2" }),
          );
        }
        if (url === "/api/v1/facts")
          return Promise.resolve(json({ items: [{ fact: item, recorded_status: "pending" }] }));
        if (url.endsWith("/fact.backend")) return Promise.resolve(json({ fact: item, events: [event(item)] }));
        if (url.includes("/attachment-targets")) return Promise.resolve(json(targets()));
        return Promise.resolve(json({}, 404));
      }),
    );

    renderRoute("/facts?fact=fact.backend", "/facts", <FactsPage />);
    expect(await screen.findByText("שיוך לפרופיל יתאפשר לאחר הקידום למקור אמת")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "קידום למקור אמת" }));
    expect(requests).toEqual([]);
    const question = screen.getByRole("dialog", { name: "לקדם את העובדה למקור אמת?" });
    fireEvent.click(within(question).getByRole("button", { name: "קידום למקור אמת" }));
    await waitFor(() => expect(requests).toContain("/api/v1/facts/fact.backend/confirm"));
  });

  it("deletes a fact from its menu only after a second question, then returns to the pool", async () => {
    const item = fact();
    const requests: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        if (init?.method === "POST") {
          requests.push(url);
          return Promise.resolve(
            json({
              fact: fact({ status: "deleted" }),
              event_id: "event-delete",
              facts_version: "facts-2",
              lifecycle_version: "lifecycle-2",
            }),
          );
        }
        if (url === "/api/v1/facts")
          return Promise.resolve(json({ items: [{ fact: item, recorded_status: "canonical" }] }));
        if (url.endsWith("/fact.backend")) return Promise.resolve(json({ fact: item, events: [event(item)] }));
        if (url.includes("/attachment-targets")) return Promise.resolve(json(targets()));
        return Promise.resolve(json({}, 404));
      }),
    );

    renderRoute("/facts?fact=fact.backend", "/facts", <FactsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "אפשרויות נוספות" }));
    fireEvent.click(
      within(screen.getByRole("dialog", { name: "פעולות על העובדה" })).getByRole("button", { name: "מחיקת העובדה" }),
    );
    expect(requests).toEqual([]);
    const question = screen.getByRole("dialog", { name: "למחוק את העובדה?" });
    fireEvent.click(within(question).getByRole("button", { name: "מחיקת העובדה" }));
    await waitFor(() => expect(requests).toContain("/api/v1/facts/fact.backend/delete"));
    expect(await screen.findByRole("heading", { level: 1, name: "מאגר העובדות" })).toBeInTheDocument();
  });
});
