import { fireEvent, screen, waitFor } from "@testing-library/react";
import { useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationListItem, Fact, FactHistory } from "@/api/contracts";
import { json, renderRoute } from "@/test/fixtures";

import { GlobalSearch } from "./GlobalSearch";

afterEach(() => {
  vi.unstubAllGlobals();
});

const openPalette = async () => {
  /* A fresh Response per call: a body is readable once, and the deferred search can ask
     more than once. */
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(json({ items: [], total: 0, limit: 8, offset: 0 }))),
  );
  renderRoute("/", "/", <GlobalSearch />);
  fireEvent.click(screen.getByRole("button", { name: "מעבר מהיר למועמדות" }));
  const field = await screen.findByRole("combobox");
  return { dialog: field.closest("dialog") as HTMLDialogElement, field };
};

const LocationProbe = () => {
  const location = useLocation();
  return <output data-testid="location">{location.pathname + location.search}</output>;
};

const application = (number: number): ApplicationListItem =>
  ({
    id: `app-${number}`,
    company: `Acme ${number}`,
    target_role: "Engineer",
    current_status: "saved",
    recruitment_status: "saved",
    preparation_state: "needs_analysis",
    content_check: "none",
    review_reasons: [],
    warnings: [],
    active_job_snapshot_id: `snapshot-${number}`,
    available_actions: ["analyze"],
    blocked_actions: [],
    recommended_action: "analyze",
    is_closed: false,
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
  }) as ApplicationListItem;

const fact: Fact = {
  fact_id: "fact.active",
  meaning: "עובדת אישור",
  renderings: { he: "עובדת אישור" },
  provenance: "אישור המועמד",
  source: "common.json",
  resume_style: "bullet",
  status: "canonical",
  tags: [],
};

const historyEvent = (id: string, factId: string): FactHistory["events"][number] => ({
  id,
  fact_id: factId,
  source: "common.json",
  event_type: "fact_confirmed",
  from_status: "pending",
  to_status: "canonical",
  application_id: null,
  claim_id: null,
  reason: "אישור בראיון",
  fact_hash: "hash",
  facts_version: "facts-1",
  lifecycle_version: "lifecycle-1",
  created_at: "2026-09-10T08:00:00Z",
});

describe("GlobalSearch", () => {
  it("opens the palette with focus in its field", async () => {
    const { dialog, field } = await openPalette();

    expect(field).toHaveFocus();
    expect(dialog.open).toBe(true);
  });

  /* Closing a modal dialog by removing it from the document leaves focus on the body.
     The element has to stay and be closed through `close()`, which is what hands focus
     back to whatever opened the palette. The browser suite asserts where focus lands;
     here the point is that the element is still there to hand it back. */
  it("closes the palette through the element rather than by unmounting it", async () => {
    const { dialog } = await openPalette();

    fireEvent.click(dialog);

    await waitFor(() => {
      expect(dialog.open).toBe(false);
    });
    expect(dialog.isConnected).toBe(true);
  });

  it("opens every application match on the paged board with the search preserved", async () => {
    const firstPage = Array.from({ length: 8 }, (_, index) => application(index + 1));
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        if (url.startsWith("/api/v1/applications")) {
          const searching = url.includes("search=Acme");
          return Promise.resolve(
            json({ items: searching ? firstPage : [], matched: searching ? 11 : 0, total: 11, limit: 8, offset: 0 }),
          );
        }
        if (url === "/api/v1/facts") return Promise.resolve(json({ items: [] }));
        if (url === "/api/v1/facts/history") return Promise.resolve(json({ events: [] }));
        return Promise.resolve(json({}, 404));
      }),
    );

    renderRoute(
      "/",
      "*",
      <>
        <GlobalSearch />
        <LocationProbe />
      </>,
    );
    fireEvent.click(screen.getByRole("button", { name: "מעבר מהיר למועמדות" }));
    fireEvent.change(await screen.findByRole("combobox"), { target: { value: "Acme" } });

    const allResults = await screen.findByRole("button", { name: "כל 11 תוצאות המועמדויות" });
    expect(screen.getAllByRole("option")).toHaveLength(8);
    fireEvent.click(allResults);
    expect(screen.getByTestId("location")).toHaveTextContent("/?activity=all&search=Acme");
  });

  it("finds facts and their exact history events while excluding deleted facts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        if (url.startsWith("/api/v1/applications")) {
          return Promise.resolve(json({ items: [], matched: 0, total: 0, limit: 8, offset: 0 }));
        }
        if (url === "/api/v1/facts") {
          return Promise.resolve(json({ items: [{ fact, recorded_status: "canonical" }] }));
        }
        if (url === "/api/v1/facts/history") {
          return Promise.resolve(
            json({
              events: [historyEvent("event-active", fact.fact_id), historyEvent("event-deleted", "fact.deleted")],
            }),
          );
        }
        return Promise.resolve(json({}, 404));
      }),
    );

    renderRoute(
      "/",
      "*",
      <>
        <GlobalSearch />
        <LocationProbe />
      </>,
    );
    fireEvent.click(screen.getByRole("button", { name: "מעבר מהיר למועמדות" }));
    const field = await screen.findByRole("combobox");
    fireEvent.change(field, { target: { value: "אישור" } });

    await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(2));
    expect(screen.getByRole("option", { name: /עובדה/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /היסטוריה/ })).toBeInTheDocument();
    fireEvent.keyDown(field, { key: "ArrowDown" });
    fireEvent.keyDown(field, { key: "Enter" });
    expect(screen.getByTestId("location")).toHaveTextContent("/facts?fact=fact.active&event=event-active");
  });
});
