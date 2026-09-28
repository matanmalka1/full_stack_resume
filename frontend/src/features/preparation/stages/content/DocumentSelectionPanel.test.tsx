import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApplicationDetail, CVDocument, Operation } from "@/api/contracts";
import { operationQueryKey } from "@/api/operations";
import { settingsQueryKey } from "@/api/settings";
import { HASH, OTHER_HASH, cvDocument, detail as baseDetail, json, settings } from "@/test/fixtures";
import { DocumentSelectionPanel } from "./DocumentSelectionPanel";

const detail = (overrides: Partial<ApplicationDetail> = {}): ApplicationDetail =>
  baseDetail({
    preparation_state: "ready_to_draft",
    content_check: "none",
    available_actions: ["update_selection", "propose_selection", "create_draft"],
    recommended_action: "create_draft",
    ...overrides,
  });

const candidates: CVDocument["selection"]["candidates"] = [
  {
    fact_id: "fact.selected",
    text: "עובדה שנבחרה",
    section: "ניסיון",
    outcome: "selected",
    reason: null,
    user_selectable: true,
  },
  {
    fact_id: "fact.omitted",
    text: "עובדה שהושמטה",
    section: "מיומנויות",
    outcome: "omitted",
    reason: "below_section_budget",
    user_selectable: true,
  },
];

const document = (overrides: Partial<CVDocument["selection"]> = {}, rest: Partial<CVDocument> = {}): CVDocument =>
  cvDocument({
    content: null,
    outline: null,
    content_check: "none",
    content_report: null,
    selection: { ...cvDocument().selection, candidates, ...overrides },
    ...rest,
  });

const operation: Operation = {
  id: "operation-1",
  application_id: "app-1",
  operation_type: "propose_selection",
  status: "queued",
  is_terminal: false,
  phase: "queued",
  message: "",
  created_at: "2026-09-06T10:00:00Z",
  outputs: [],
  available_actions: ["cancel"],
};

const mutation = {
  application_id: "app-1",
  document_id: "doc-1",
  document_hash: OTHER_HASH,
  document_state: "draft",
  content_check: "none",
  pending_claim_ids: [],
};

const panel = (client: QueryClient, value: ApplicationDetail, doc: CVDocument, onQueued: (id: string) => void) => (
  <QueryClientProvider client={client}>
    <DocumentSelectionPanel
      detail={value}
      document={doc}
      emphasized={false}
      onQueued={onQueued}
      operationLive={false}
      requirements={[
        {
          requirementId: "requirement-1",
          text: "Priority ERP",
          importance: "mandatory",
          coverage: "matched",
          shortfallSeverity: null,
          shortfallReason: null,
          supportingFactIds: ["fact.omitted"],
          boundaryFactIds: [],
        },
      ]}
    />
  </QueryClientProvider>
);

const renderPanel = (value: ApplicationDetail, doc: CVDocument, ai: boolean, onQueued = vi.fn()) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchInterval: false }, mutations: { retry: false } },
  });
  client.setQueryData(settingsQueryKey, {
    settings: settings({ ai_enabled: ai, provider_configured: ai }),
    etag: '"settings-1"',
  });
  const rendered = render(panel(client, value, doc, onQueued));
  return {
    client,
    onQueued,
    rerender: (next: CVDocument) => rendered.rerender(panel(client, value, next, onQueued)),
  };
};

const postBody = (fetchMock: ReturnType<typeof vi.fn>) => {
  const post = fetchMock.mock.calls.find((call) => (call[1] as RequestInit | undefined)?.method === "POST");
  return { url: String(post?.[0]), body: JSON.parse(String((post?.[1] as RequestInit | undefined)?.body)) };
};

afterEach(() => vi.unstubAllGlobals());

describe("DocumentSelectionPanel", () => {
  it("saves absolute manual choices against the document hash it was read with", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(mutation));
    vi.stubGlobal("fetch", fetchMock);
    renderPanel(detail(), document(), false);

    const sectionToggle = screen.getByRole("button", { name: /^מיומנויות/ });
    fireEvent.click(sectionToggle);
    const row = screen.getByText("עובדה שהושמטה").closest("li");
    if (row === null) throw new Error("candidate row was not rendered");
    expect(within(row).getByRole("radio", { name: "אוטומטי" })).toBeChecked();
    fireEvent.click(within(row).getByRole("radio", { name: "הכללה" }));
    fireEvent.click(screen.getByRole("button", { name: "שמירת בחירת העובדות" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const { url, body } = postBody(fetchMock);
    expect(url).toBe("/api/v1/applications/app-1/document/selection");
    expect(body).toEqual({ expected_document_hash: HASH, pinned_fact_ids: ["fact.omitted"], excluded_fact_ids: [] });
  });

  it("offers nothing to save until a choice changed", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderPanel(detail(), document(), false);

    expect(screen.getByRole("button", { name: "שמירת בחירת העובדות" })).toBeDisabled();
  });

  it("queues an AI proposal addressed to the exact document", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json(operation, 202, { Location: "/api/v1/operations/operation-1" }));
    vi.stubGlobal("fetch", fetchMock);
    const { onQueued } = renderPanel(detail(), document(), true);

    fireEvent.click(screen.getByRole("button", { name: "הצעת בחירה באמצעות AI" }));

    await waitFor(() => expect(onQueued).toHaveBeenCalledWith("operation-1"));
    const { url, body } = postBody(fetchMock);
    expect(url).toBe("/api/v1/applications/app-1/document/selection-proposals");
    expect(body).toEqual({ expected_document_hash: HASH });
    const headers = (fetchMock.mock.calls[0]![1] as RequestInit).headers;
    expect(headers).toBeInstanceOf(Headers);
    expect((headers as Headers).get("Idempotency-Key")).not.toBeNull();
  });

  it("withholds the AI proposal when the projection does not offer it", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderPanel(detail({ available_actions: ["update_selection"] }), document(), true);

    expect(screen.queryByRole("button", { name: "הצעת בחירה באמצעות AI" })).toBeNull();
    expect(screen.getByText("הצעת AI אינה זמינה למסמך במצבו הנוכחי.")).toBeInTheDocument();
  });

  it("shows an AI selection's own rationale and labels only the marks it still holds", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderPanel(
      detail(),
      document({
        pinned_fact_ids: ["fact.omitted"],
        excluded_fact_ids: ["fact.selected"],
        proposed_by: "ai",
        proposal_rationale: "Pinned the skills fact because the posting asks for it.",
      }),
      false,
    );

    expect(screen.getByText("Pinned the skills fact because the posting asks for it.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^מיומנויות/ }));
    fireEvent.click(screen.getByRole("button", { name: /^ניסיון/ }));
    const pinnedRow = screen.getByText("עובדה שהושמטה").closest("li");
    if (pinnedRow === null) throw new Error("candidate rows were not rendered");
    expect(within(pinnedRow).getByText(/מהצעת AI/)).toBeInTheDocument();

    fireEvent.click(within(pinnedRow).getByRole("radio", { name: "אוטומטי" }));
    expect(within(pinnedRow).queryByText(/מהצעת AI/)).toBeNull();
  });

  it("reports which facts an AI proposal added and removed once the document reflects it", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
      Promise.resolve(
        init?.method === "POST"
          ? json(operation, 202, { Location: "/api/v1/operations/operation-1" })
          : json({ ...operation, status: "succeeded", is_terminal: true, available_actions: [] }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { client, onQueued, rerender } = renderPanel(detail(), document(), true);

    fireEvent.click(screen.getByRole("button", { name: "הצעת בחירה באמצעות AI" }));
    await waitFor(() => expect(onQueued).toHaveBeenCalledWith("operation-1"));

    const finished = { ...operation, status: "succeeded", is_terminal: true, available_actions: [] } as Operation;
    client.setQueryData(operationQueryKey("operation-1"), finished);
    rerender(
      document(
        {
          pinned_fact_ids: ["fact.omitted"],
          excluded_fact_ids: ["fact.selected"],
          proposed_by: "ai",
          candidates: [
            { ...candidates[0]!, outcome: "omitted", reason: "excluded_by_user" },
            { ...candidates[1]!, outcome: "pinned", reason: null },
          ],
        },
        { document_hash: OTHER_HASH },
      ),
    );

    expect(await screen.findByText("ההצעה שינתה 2 עובדות בקורות החיים:")).toBeInTheDocument();
    const added = screen.getByRole("heading", { name: "נוספו לקורות החיים (1)" }).parentElement;
    if (added === null) throw new Error("the added list was not rendered");
    expect(within(added).getByText("עובדה שהושמטה")).toBeInTheDocument();
    expect(within(added).getByText("Priority ERP")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "הוסרו מקורות החיים (1)" })).toBeInTheDocument();
  });
});
