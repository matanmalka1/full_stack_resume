import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Fact } from "@/api/contracts";
import { json, renderRoute } from "@/test/fixtures";
import { FactsPage } from "./FactsPage";

const fact = (overrides: Partial<Fact> = {}): Fact => ({
  fact_id: "fact.backend",
  meaning: "Built backend services",
  provenance: "Confirmed by candidate",
  renderings: { en: "Built backend services", he: "בניית שירותי Backend" },
  resume_style: "bullet",
  source: "development.md",
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

afterEach(() => vi.unstubAllGlobals());

describe("FactsPage", () => {
  it("shows a reconciliation blocker when the store and lifecycle trail disagree", async () => {
    const item = fact();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        if (url === "/api/v1/facts")
          return Promise.resolve(json({ items: [{ fact: item, recorded_status: "confirmed" }] }));
        if (url.endsWith("/fact.backend")) return Promise.resolve(json({ fact: item, events: [event(item)] }));
        if (url.includes("/attachment-targets")) return Promise.resolve(json(targets()));
        return Promise.resolve(json({}, 404));
      }),
    );

    renderRoute("/facts", "/facts", <FactsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("נמצאה אי־התאמה ביומן העובדות");
    expect(screen.queryByText("הוספת עובדה חדשה")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "צירוף העובדה לסעיף" })).not.toBeInTheDocument();
  });

  it("shows a load failure without presenting an empty pool", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(json({ detail: "failed" }, 500))),
    );
    renderRoute("/facts", "/facts", <FactsPage />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.queryByText("לא נמצאו עובדות התואמות למסננים.")).not.toBeInTheDocument();
  });

  it("deep-links a fact and filters the candidate pool without another API surface", async () => {
    const backend = fact();
    const sales = fact({
      fact_id: "fact.sales",
      meaning: "Managed accounts",
      renderings: { en: "Managed accounts" },
      source: "sales.md",
      status: "pending",
      tags: ["sales"],
    });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        if (url === "/api/v1/facts")
          return Promise.resolve(
            json({ items: [backend, sales].map((item) => ({ fact: item, recorded_status: item.status })) }),
          );
        if (url.includes("/attachment-targets")) return Promise.resolve(json(targets()));
        if (url.endsWith("/fact.backend")) return Promise.resolve(json({ fact: backend, events: [event(backend)] }));
        if (url.endsWith("/fact.sales")) return Promise.resolve(json({ fact: sales, events: [event(sales)] }));
        return Promise.resolve(json({}, 404));
      }),
    );

    renderRoute("/facts?fact=fact.backend", "/facts", <FactsPage />);

    expect(await screen.findByRole("link", { name: /בניית שירותי Backend/ })).toHaveAttribute("aria-current", "true");
    /* The selected fact leads with the English rendering - the one a CV is built from -
       and keeps the Hebrew one under it. */
    expect(screen.getByRole("heading", { name: "Built backend services" })).toBeInTheDocument();
    expect(screen.getAllByText("בניית שירותי Backend").length).toBeGreaterThan(0);
    expect(screen.getByText("משמעות עובדתית")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("מעמד"), { target: { value: "pending" } });
    expect(screen.getByText("Managed accounts")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /בניית שירותי Backend/ })).not.toBeInTheDocument();
  });

  it("uses explicit promotion, replacement, and attachment commands", async () => {
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
    await screen.findByRole("link", { name: /בניית שירותי Backend/ });

    fireEvent.click(await screen.findByRole("button", { name: "צירוף העובדה לסעיף" }));
    await waitFor(() => expect(requests.some((request) => request.url.endsWith("/attachments"))).toBe(true));
    expect(requests.find((request) => request.url.endsWith("/attachments"))?.body).toEqual({
      pin: false,
      profile: "development",
      section: "Experience",
    });

    fireEvent.click(screen.getByText("יצירת תיקון לעובדה"));
    fireEvent.click(screen.getByRole("button", { name: "יצירת עובדת תיקון ממתינה" }));
    await waitFor(() => expect(requests.some((request) => request.url === "/api/v1/facts")).toBe(true));
    const correction = requests.find((request) => request.url === "/api/v1/facts");
    expect(correction?.body).toMatchObject({
      replaces: "fact.backend",
      reason: "canonical correction created from the candidate facts page",
    });
  });

  it.each([
    ["pending", "אישור העובדה", "confirm"],
    ["confirmed", "קידום למקור אמת", "promote"],
  ] as const)("requires attestation before moving a %s fact", async (status, label, command) => {
    const item = fact({ status });
    const requests: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request, init?: RequestInit) => {
        const url = String(input);
        if (init?.method === "POST") {
          requests.push(url);
          const next = fact({ status: command === "confirm" ? "confirmed" : "canonical" });
          return Promise.resolve(
            json({ fact: next, event_id: "event-next", facts_version: "facts-2", lifecycle_version: "lifecycle-2" }),
          );
        }
        if (url === "/api/v1/facts") return Promise.resolve(json({ items: [{ fact: item, recorded_status: status }] }));
        if (url.endsWith("/fact.backend")) return Promise.resolve(json({ fact: item, events: [event(item)] }));
        if (url.includes("/attachment-targets")) return Promise.resolve(json(targets()));
        return Promise.resolve(json({}, 404));
      }),
    );

    renderRoute("/facts?fact=fact.backend", "/facts", <FactsPage />);
    const button = await screen.findByRole("button", { name: label });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: /בדקתי את תוכן העובדה/ }));
    fireEvent.click(button);
    await waitFor(() => expect(requests).toContain(`/api/v1/facts/fact.backend/${command}`));
  });
});
