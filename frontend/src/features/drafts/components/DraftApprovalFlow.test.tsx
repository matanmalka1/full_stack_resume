import { useQuery } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { applicationDetailQueryOptions } from "@/api/applications";
import type { ApplicationDetail } from "@/api/contracts";
import { documentQueryOptions } from "@/api/documents";
import { HASH, OTHER_HASH, cvDocument, detail, documentCheck, json, operation, renderRoute } from "@/test/fixtures";
import { DraftApprovalDialog } from "./DraftApprovalDialog";
import { DraftApprovalBar } from "./DraftApprovalBar";
import { DraftRenderPanel } from "./DraftRenderPanel";
import { DraftValidationPanel } from "./DraftValidationPanel";
import { useDocumentCheck } from "../hooks/useDocumentCheck";
import { useRenderDocument } from "../hooks/useRenderDocument";
import { isEditable } from "../model/drafts.types";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

/* Checking, approval, and render are panels of the draft editor rather than screens of
   their own. These exercise them at the boundaries the editor is held to: the exact hash
   each command names, the report approval is offered on, and the refusal paths. */

const isPost = (init?: RequestInit) => init?.method === "POST";
const approvedDetail = detail({
  preparation_state: "approved",
  available_actions: ["edit", "render"],
  recommended_action: "render",
  approved_at: "2026-08-24T00:00:00Z",
});

/* The render step as the editor composes it: the command held by the host, the panel
   drawing its state. The editor's watch reports a queued render as `rendering`, so the
   harness does the same with the id it was handed. */
const RenderStep = ({
  autoStart = false,
  detail: projection,
  onQueued,
}: {
  autoStart?: boolean;
  detail: ApplicationDetail;
  onQueued: (operationId: string) => void;
}) => {
  const [queued, setQueued] = useState<string | null>(null);
  const state = useRenderDocument({
    autoStart,
    detail: projection,
    onQueued: (operationId) => {
      setQueued(operationId);
      onQueued(operationId);
    },
    rendering: queued !== null,
  });
  return <DraftRenderPanel applicationId="app-1" lastRenderError={null} state={state} />;
};

/* A harness standing in for the editor: it holds the document, reads the stored check
   through the same hook the editor uses, and owns the approval control and the dialog
   exactly as DraftEditorPage does. */
const DraftFlow = () => {
  const [open, setOpen] = useState(false);
  const [approved, setApproved] = useState(false);
  const detailQuery = useQuery(applicationDetailQueryOptions("app-1"));
  const documentQuery = useQuery(documentQueryOptions("app-1"));
  const document = documentQuery.data?.document;
  const draft = document !== undefined && isEditable(document) ? document : undefined;
  const check = useDocumentCheck("app-1", draft);

  return (
    <>
      <DraftValidationPanel check={check} />
      {/* The editor exposes one finish action: it checks first and opens the explicit
          approval only when the stored report passed against the document on screen. */}
      <button
        disabled={!check.canCheck && !check.passing}
        onClick={check.passing ? () => setOpen(true) : check.check}
        type="button"
      >
        {check.passing ? "אישור והכנת PDF" : "בדיקה והכנת PDF"}
      </button>
      <DraftApprovalDialog
        applicationId="app-1"
        detail={detailQuery.data}
        draft={draft}
        onApproved={() => {
          setOpen(false);
          setApproved(true);
        }}
        onCheckFailed={() => setOpen(false)}
        onClose={() => setOpen(false)}
        onStale={() => {
          setOpen(false);
          check.reportStaleRefusal();
        }}
        open={open}
      />
      {approved ? <RenderStep detail={approvedDetail} onQueued={() => {}} /> : null}
    </>
  );
};

describe("DraftValidationPanel", () => {
  it("keeps the check available after a stale approval refusal", () => {
    render(
      <MemoryRouter>
        <DraftApprovalBar
          applicationHref="/applications/app-1"
          onApprove={vi.fn()}
          onValidate={vi.fn()}
          passing={false}
          reviewBlocked={false}
          stale
          validationPending={false}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: "בדיקה מחדש והכנת PDF" })).toBeEnabled();
  });

  it("renders hard issues as blockers and soft issues as warnings without dropping unknown values", async () => {
    const report = {
      passed: false,
      groups: { unknown_group: false },
      evidence: { opaque: true },
      issues: [
        { group: "unknown_group", code: "UNKNOWN_HARD", hard: true, message: "Hard issue" },
        { group: "unknown_group", code: "UNKNOWN_SOFT", hard: false, message: "Soft issue" },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) =>
        Promise.resolve(
          json(
            String(input).endsWith("/document")
              ? cvDocument({ content_check: "failed", content_report: report })
              : detail({ content_check: "failed" }),
          ),
        ),
      ),
    );
    renderRoute("/applications/app-1/draft", "/applications/:applicationId/draft", <DraftFlow />);
    expect(await screen.findByText("Hard issue", {}, { timeout: 5_000 })).toBeInTheDocument();
    expect(
      within(screen.getByRole("heading", { name: "נדרשים תיקונים בקובץ" }).closest("section")!).getByText("Soft issue"),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "נדרשים תיקונים בקובץ" })).toBeInTheDocument();
    /* An unknown code is not dropped - its message is rendered above - but the code
       itself is not shown: it names the failure in a vocabulary the reader has no use for. */
    expect(screen.queryByText(/UNKNOWN_HARD/)).toBeNull();
    expect(screen.getByRole("button", { name: "בדיקה והכנת PDF" })).toBeInTheDocument();
  });

  it("checks the exact document hash and offers approval only once the stored report passed", async () => {
    let checked = false;
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (isPost(init)) {
        checked = true;
        return Promise.resolve(json(documentCheck()));
      }
      return Promise.resolve(
        json(
          url.endsWith("/document")
            ? cvDocument(checked ? {} : { content_check: "none", content_report: null })
            : detail({ content_check: checked ? "passed" : "none" }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/applications/app-1/draft", "/applications/:applicationId/draft", <DraftFlow />);
    const checkButton = await screen.findByRole("button", { name: "בדיקה והכנת PDF" });
    await waitFor(() => expect(checkButton).toBeEnabled());
    fireEvent.click(checkButton);
    await screen.findByRole("button", { name: "אישור והכנת PDF" });
    const request = fetchMock.mock.calls.find((call) => isPost(call[1]));
    expect(String(request?.[0])).toContain("/applications/app-1/document/check");
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ expected_document_hash: HASH });
  });

  it("does not let a late passing check describe a document edited since", async () => {
    let finishCheck: (response: Response) => void = () => {};
    const response = new Promise<Response>((resolve) => {
      finishCheck = resolve;
    });
    let edited = false;
    const fetchMock = vi.fn((input: unknown, init?: RequestInit) => {
      const url = String(input);
      if (isPost(init)) return response;
      if (url.endsWith("/document"))
        return Promise.resolve(
          json(
            edited
              ? cvDocument({
                  document_hash: OTHER_HASH,
                  content_check: "failed",
                  content_report: { passed: false, groups: {}, evidence: {}, issues: [] },
                })
              : cvDocument({ content_check: "none", content_report: null }),
          ),
        );
      return Promise.resolve(json(detail({ document_hash: edited ? OTHER_HASH : HASH })));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/applications/app-1/draft", "/applications/:applicationId/draft", <DraftFlow />);
    const checkButton = await screen.findByRole("button", { name: "בדיקה והכנת PDF" });
    await waitFor(() => expect(checkButton).toBeEnabled());
    fireEvent.click(checkButton);
    edited = true;
    await act(async () => finishCheck(json(documentCheck())));
    expect(await screen.findByRole("heading", { name: "נדרשים תיקונים בקובץ" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "הקובץ עבר בדיקה" })).toBeNull();
    expect(screen.getByRole("button", { name: "בדיקה והכנת PDF" })).toBeEnabled();
  });
});

describe("DraftApprovalDialog", () => {
  it("requires the local warning checkbox and approves the exact document hash", async () => {
    const warned = cvDocument({
      content_report: {
        passed: true,
        groups: {},
        evidence: {},
        issues: [{ group: "copy", code: "SOFT", hard: false, message: "Review wording" }],
      },
    });
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (isPost(init))
        return Promise.resolve(
          json(documentCheck({ preparation_state: "approved", approved_at: "2026-08-24T00:00:00Z" })),
        );
      return Promise.resolve(json(url.endsWith("/document") ? warned : detail()));
    });
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/applications/app-1/draft", "/applications/:applicationId/draft", <DraftFlow />);
    const openApproval = await screen.findByRole("button", { name: "אישור והכנת PDF" });
    await waitFor(() => expect(openApproval).toBeEnabled());
    fireEvent.click(openApproval);
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Acme");
    expect(dialog).toHaveTextContent("Engineer");
    expect(dialog).toHaveTextContent(HASH.slice(0, 12));
    const approve = within(dialog).getByRole("button", { name: "אישור והכנת PDF" });
    expect(approve).toBeDisabled();
    fireEvent.click(within(dialog).getByRole("checkbox"));
    fireEvent.click(approve);
    /* Approval is synchronous and succeeded, so the editor moves to its render step in place. */
    expect(await screen.findByRole("heading", { name: "הגרסה אושרה" })).toBeInTheDocument();
    const request = fetchMock.mock.calls.find((call) => isPost(call[1]));
    expect(String(request?.[0])).toContain("/applications/app-1/document/approve");
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ expected_document_hash: HASH });
  });

  it("shows a blocker refusal inside the open approval dialog", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request, init?: RequestInit) =>
        isPost(init)
          ? Promise.resolve(
              json(
                {
                  type: "about:blank",
                  title: "Precondition Failed",
                  status: 412,
                  code: "KNOWLEDGE_RECONCILIATION_REQUIRED",
                  detail: "reconcile first",
                },
                412,
              ),
            )
          : Promise.resolve(json(String(input).endsWith("/document") ? cvDocument() : detail())),
      ),
    );
    renderRoute("/applications/app-1/draft", "/applications/:applicationId/draft", <DraftFlow />);
    const openApproval = await screen.findByRole("button", { name: "אישור והכנת PDF" });
    await waitFor(() => expect(openApproval).toBeEnabled());
    fireEvent.click(openApproval);
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "אישור והכנת PDF" }));
    const dialog = await screen.findByRole("dialog");
    /* A known code, so the callout shows the client's own translation. */
    expect(await within(dialog).findByText(/יש להשלים את התאמת מאגר העובדות לפני שממשיכים/)).toBeInTheDocument();
    expect(dialog).toHaveAttribute("open");
  });

  it("returns DOCUMENT_CHANGED to the check panel without retrying automatically", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) =>
      isPost(init)
        ? Promise.resolve(
            json(
              { type: "about:blank", title: "Conflict", status: 409, code: "DOCUMENT_CHANGED", detail: "changed" },
              409,
            ),
          )
        : Promise.resolve(json(String(input).endsWith("/document") ? cvDocument() : detail())),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/applications/app-1/draft", "/applications/:applicationId/draft", <DraftFlow />);
    const openApproval = await screen.findByRole("button", { name: "אישור והכנת PDF" });
    await waitFor(() => expect(openApproval).toBeEnabled());
    fireEvent.click(openApproval);
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "אישור והכנת PDF" }));
    /* The panel says the document moved on; nothing re-checked or re-approved by itself. */
    expect(await screen.findByText("הטיוטה השתנתה מאז הבדיקה")).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter((call) => isPost(call[1]))).toHaveLength(1);
  });
});

describe("DraftRenderPanel", () => {
  const renderFetch = () =>
    vi.fn((_input: string | URL | Request, init?: RequestInit) =>
      isPost(init)
        ? Promise.resolve(json(operation(), 202, { Location: "/api/v1/operations/op-render" }))
        : Promise.resolve(json(detail())),
    );

  /* Rendering reports the Operation it queued to the screen holding the panel rather than
     navigating to it: the approved document stays on screen while the file is produced. */
  it("renders the approved document hash and hands the accepted Operation to its host", async () => {
    const fetchMock = renderFetch();
    vi.stubGlobal("fetch", fetchMock);
    const onQueued = vi.fn();
    renderRoute(
      "/applications/app-1/draft",
      "/applications/:applicationId/draft",
      <RenderStep detail={approvedDetail} onQueued={onQueued} />,
    );
    const renderButton = await screen.findByRole("button", { name: "יצירת HTML ו־PDF" });
    await waitFor(() => expect(renderButton).toBeEnabled());
    fireEvent.click(renderButton);
    await waitFor(() => expect(onQueued).toHaveBeenCalledWith(operation().id));
    const request = fetchMock.mock.calls.find((call) => isPost(call[1]));
    expect(String(request?.[0])).toContain("/applications/app-1/document/render");
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ expected_document_hash: HASH });
    expect(new Headers(request?.[1]?.headers).get("Idempotency-Key")).toBe(`render:${HASH}`);
  });

  it("starts rendering without another confirmation when reached from approval", async () => {
    const fetchMock = renderFetch();
    vi.stubGlobal("fetch", fetchMock);
    const onQueued = vi.fn();

    renderRoute(
      "/applications/app-1/draft",
      "/applications/:applicationId/draft",
      <RenderStep autoStart detail={approvedDetail} onQueued={onQueued} />,
    );

    await waitFor(() => expect(onQueued).toHaveBeenCalledWith(operation().id));
    expect(fetchMock.mock.calls.filter((call) => isPost(call[1]))).toHaveLength(1);
    /* While it renders the panel steps aside for the editor's inline Operation report, and
       offers no second way to start the same work. */
    expect(screen.queryByRole("heading", { name: "הגרסה אושרה" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "יצירת HTML ו־PDF" })).not.toBeInTheDocument();
  });

  it("offers the ready step once the projection says the document is Ready", async () => {
    vi.stubGlobal("fetch", renderFetch());

    renderRoute(
      "/applications/app-1/draft",
      "/applications/:applicationId/draft",
      <RenderStep detail={detail({ preparation_state: "ready" })} onQueued={vi.fn()} />,
    );

    expect(await screen.findByRole("link", { name: "מעבר לקורות החיים המוכנים" })).toHaveAttribute(
      "href",
      "/applications/app-1/ready",
    );
    expect(screen.getByText("שלב הטיוטה הושלם.")).toBeInTheDocument();
  });
});
