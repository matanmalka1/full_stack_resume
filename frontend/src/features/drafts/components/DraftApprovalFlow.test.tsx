import { useQuery } from "@tanstack/react-query";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { applicationDetailQueryOptions } from "@/api/applications";
import { workingDraftQueryOptions } from "@/api/drafts";
import { detail, draft, json, operation, renderRoute, revision, validation } from "@/test/fixtures";
import { DraftApprovalDialog } from "./DraftApprovalDialog";
import { DraftRenderPanel } from "./DraftRenderPanel";
import { DraftValidationPanel } from "./DraftValidationPanel";
import { useDraftValidation } from "../hooks/useDraftValidation";

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

/* Validation, approval, and render are panels of the draft editor rather than screens
   of their own. The behavior each one owns is unchanged, so these exercise the components
   at the same boundaries the screens were held to: the exact payload sent, the exact run
   approval is offered for, and the two refusal paths. */

/* A harness standing in for the editor: it holds the draft, derives the exact passing run
   from the same hook the editor uses, and owns the approval control and the dialog exactly
   as DraftEditorPage does. */
const DraftFlow = () => {
  const [open, setOpen] = useState(false);
  const [approved, setApproved] = useState<string | null>(null);
  /* The editor watches the work its panels queue rather than navigating to it, so the
     harness records the queued id the same way. */
  const [queued, setQueued] = useState<string | null>(null);
  const detailQuery = useQuery(applicationDetailQueryOptions("app-1"));
  const draftQuery = useQuery(workingDraftQueryOptions("draft-1"));
  const validation = useDraftValidation("app-1", draftQuery.data?.draft);

  return (
    <>
      <DraftValidationPanel validation={validation} />
      {/* Approval sits beside the report rather than inside it: the panel draws a verdict
          and the screen holding it decides what that verdict opens. */}
      <button disabled={validation.exactPassingRunId === null} onClick={() => setOpen(true)} type="button">
        פתיחת אישור
      </button>
      <DraftApprovalDialog
        applicationId="app-1"
        detail={detailQuery.data}
        draft={draftQuery.data?.draft}
        onApproved={(revisionId) => {
          setOpen(false);
          setApproved(revisionId);
        }}
        onClose={() => setOpen(false)}
        onStale={() => {
          setOpen(false);
          validation.reportStaleRefusal();
        }}
        open={open}
        validationRunId={validation.exactPassingRunId}
      />
      {approved === null ? null : <DraftRenderPanel approvedRevisionId={approved} onQueued={setQueued} />}
      {queued === null ? null : <p>{`בעבודה: ${queued}`}</p>}
    </>
  );
};

describe("DraftValidationPanel", () => {
  it("renders hard issues as blockers and soft issues as warnings without dropping unknown values", async () => {
    const run = validation({
      passed: false,
      report: {
        passed: false,
        groups: { unknown_group: false },
        evidence: { opaque: true },
        issues: [
          { group: "unknown_group", code: "UNKNOWN_HARD", hard: true, message: "Hard issue" },
          { group: "unknown_group", code: "UNKNOWN_SOFT", hard: false, message: "Soft issue" },
        ],
      },
    });
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request) =>
        Promise.resolve(
          json(
            String(input).includes("validation-runs")
              ? run
              : String(input).includes("working-drafts")
                ? draft()
                : detail({ working_draft_state: "validation_failed" }),
          ),
        ),
      ),
    );
    renderRoute("/applications/app-1/draft", "/applications/:applicationId/draft", <DraftFlow />);
    /* The report waits for detail, draft, and validation-run queries. Parallel execution
       of the full frontend suite can schedule that chain beyond the one-second default;
       the focused timeout still fails promptly if the report never arrives. */
    expect(await screen.findByText("Hard issue", {}, { timeout: 5_000 })).toBeInTheDocument();
    expect(screen.getByText("Soft issue")).toBeInTheDocument();
    /* An unknown code is not dropped - its message is rendered above - but the code
       itself is not shown: `UNKNOWN_HARD` names the failure in a vocabulary the reader
       has no use for, and the message beside it already says what went wrong. */
    expect(screen.queryByText(/UNKNOWN_HARD/)).toBeNull();
    expect(screen.getByRole("button", { name: "אימות מחדש" })).toBeInTheDocument();
  });

  it("posts the exact edit version and exposes approval only after a passing response", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST") return Promise.resolve(json(validation()));
      return Promise.resolve(
        json(
          url.includes("working-drafts")
            ? draft({ latest_validation_run_id: null })
            : detail({ working_draft_state: "editing" }),
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/applications/app-1/draft", "/applications/:applicationId/draft", <DraftFlow />);
    const validate = await screen.findByRole("button", { name: "אימות הטיוטה" });
    await waitFor(() => expect(validate).toBeEnabled());
    /* Approval is closed until a passing run for this exact version exists. */
    expect(screen.getByRole("button", { name: "פתיחת אישור" })).toBeDisabled();
    fireEvent.click(validate);
    await waitFor(() => expect(screen.getByRole("button", { name: "פתיחת אישור" })).toBeEnabled());
    const request = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ expected_edit_version: 4 });
  });
});

describe("DraftApprovalDialog", () => {
  it("requires the local warning checkbox and never sends an acknowledgement field", async () => {
    const warned = validation({
      report: {
        passed: true,
        groups: {},
        evidence: {},
        issues: [{ group: "copy", code: "SOFT", hard: false, message: "Review wording" }],
      },
    });
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "POST")
        return Promise.resolve(
          json(
            {
              revision_id: "revision-1",
              application_id: "app-1",
              version: 1,
              decision_record_id: "decision-1",
              markdown_artifact_version_id: "md-1",
              manifest_artifact_version_id: "manifest-1",
            },
            201,
          ),
        );
      return Promise.resolve(
        json(url.includes("validation-runs") ? warned : url.includes("working-drafts") ? draft() : detail()),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/applications/app-1/draft", "/applications/:applicationId/draft", <DraftFlow />);
    const openApproval = await screen.findByRole("button", { name: "פתיחת אישור" });
    await waitFor(() => expect(openApproval).toBeEnabled());
    fireEvent.click(openApproval);
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Acme");
    expect(dialog).toHaveTextContent("Engineer");
    expect(dialog).toHaveTextContent("4");
    /* The validation run id is no longer shown. What matters about it is that approval
       is bound to that exact run, and the request assertion at the end of this test is
       what proves it - the collapsed identifier only proved it had been printed. */
    expect(screen.queryByText("run-1")).toBeNull();
    const approve = await screen.findByRole("button", { name: "אישור הגרסה" });
    expect(approve).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(approve);
    /* Approval succeeded, so the editor moves to its render step in place. */
    expect(await screen.findByRole("heading", { name: "הגרסה אושרה" })).toBeInTheDocument();
    const request = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({
      expected_edit_version: 4,
      validation_run_id: "run-1",
    });
  });

  it("shows a non-stale approval failure inside the open trust-boundary dialog", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request, init?: RequestInit) =>
        init?.method === "POST"
          ? Promise.resolve(
              json(
                {
                  type: "about:blank",
                  title: "Conflict",
                  status: 409,
                  code: "STATE_CONFLICT",
                  detail: "approval changed",
                },
                409,
              ),
            )
          : Promise.resolve(
              json(
                String(input).includes("validation-runs")
                  ? validation()
                  : String(input).includes("working-drafts")
                    ? draft()
                    : detail(),
              ),
            ),
      ),
    );
    renderRoute("/applications/app-1/draft", "/applications/:applicationId/draft", <DraftFlow />);
    const openApproval = await screen.findByRole("button", { name: "פתיחת אישור" });
    await waitFor(() => expect(openApproval).toBeEnabled());
    fireEvent.click(openApproval);
    fireEvent.click(await screen.findByRole("button", { name: "אישור הגרסה" }));
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("approval changed");
    expect(dialog).toHaveAttribute("open");
  });

  it("gives direct recovery for a preserved out-of-band Markdown edit", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: string | URL | Request, init?: RequestInit) =>
        init?.method === "POST"
          ? Promise.resolve(
              json(
                {
                  type: "about:blank",
                  title: "Conflict",
                  status: 409,
                  code: "WORKING_PROJECTION_DIVERGED",
                  detail: "projection differs",
                },
                409,
              ),
            )
          : Promise.resolve(
              json(
                String(input).includes("validation-runs")
                  ? validation()
                  : String(input).includes("working-drafts")
                    ? draft()
                    : detail(),
              ),
            ),
      ),
    );
    renderRoute("/applications/app-1/draft", "/applications/:applicationId/draft", <DraftFlow />);
    const openApproval = await screen.findByRole("button", { name: "פתיחת אישור" });
    await waitFor(() => expect(openApproval).toBeEnabled());
    fireEvent.click(openApproval);
    fireEvent.click(await screen.findByRole("button", { name: "אישור הגרסה" }));

    expect(await screen.findByText("נמצא שינוי בקובץ העבודה שלא יובא לטיוטה")).toBeInTheDocument();
    expect(screen.getByText(/השינוי נשמר ולא נדרס/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "חזרה לעורך" })).toBeInTheDocument();
    expect(screen.queryByText("projection differs")).not.toBeInTheDocument();
  });

  it("returns VALIDATION_STALE to the validation panel without retrying automatically", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) =>
      init?.method === "POST"
        ? Promise.resolve(
            json(
              {
                type: "about:blank",
                title: "Stale",
                status: 412,
                code: "VALIDATION_STALE",
                detail: "stale",
              },
              412,
            ),
          )
        : Promise.resolve(
            json(
              String(input).includes("validation-runs")
                ? validation()
                : String(input).includes("working-drafts")
                  ? draft()
                  : detail(),
            ),
          ),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderRoute("/applications/app-1/draft", "/applications/:applicationId/draft", <DraftFlow />);
    const openApproval = await screen.findByRole("button", { name: "פתיחת אישור" });
    await waitFor(() => expect(openApproval).toBeEnabled());
    fireEvent.click(openApproval);
    fireEvent.click(await screen.findByRole("button", { name: "אישור הגרסה" }));
    /* The panel says the draft moved on; nothing re-validated or re-approved by itself. */
    expect(await screen.findByText("הטיוטה השתנתה מאז האימות")).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1);
  });
});

describe("DraftRenderPanel", () => {
  /* Rendering reports the Operation it queued to the screen holding the panel rather
     than navigating to the Operation's own route: the approved draft stays on screen
     while the file is produced. What the panel owes its host is the queued id, so that
     is what this asserts, alongside the exact payload it sent. */
  it("renders with the explicit application ID and hands the accepted Operation to its host", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) =>
      init?.method === "POST"
        ? Promise.resolve(json(operation(), 202, { Location: "/api/v1/operations/op-render" }))
        : Promise.resolve(
            json(
              revision({
                ready_qualified: false,
                html_artifact_version_id: null,
                pdf_artifact_version_id: null,
              }),
            ),
          ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const onQueued = vi.fn();
    renderRoute(
      "/applications/app-1/draft",
      "/applications/:applicationId/draft",
      <DraftRenderPanel approvedRevisionId="revision-1" onQueued={onQueued} />,
    );
    const renderButton = await screen.findByRole("button", { name: "יצירת HTML ו־PDF" });
    await waitFor(() => expect(renderButton).toBeEnabled());
    fireEvent.click(renderButton);
    await waitFor(() => expect(onQueued).toHaveBeenCalledWith(operation().id));
    const request = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({ application_id: "app-1" });
  });

  it("starts rendering without another confirmation when reached from approval", async () => {
    const fetchMock = vi.fn((input: string | URL | Request, init?: RequestInit) =>
      init?.method === "POST"
        ? Promise.resolve(json(operation(), 202, { Location: "/api/v1/operations/op-render" }))
        : Promise.resolve(
            json(
              revision({
                ready_qualified: false,
                html_artifact_version_id: null,
                pdf_artifact_version_id: null,
              }),
            ),
          ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const onQueued = vi.fn();

    renderRoute(
      "/applications/app-1/draft",
      "/applications/:applicationId/draft",
      <DraftRenderPanel approvedRevisionId="revision-1" autoStart onQueued={onQueued} />,
    );

    await waitFor(() => expect(onQueued).toHaveBeenCalledWith(operation().id));
    expect(fetchMock.mock.calls.filter((call) => call[1]?.method === "POST")).toHaveLength(1);
  });

  it("keeps the completed render transition in the wizard action bar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          json(
            revision({
              ready_qualified: true,
              html_artifact_version_id: "html-1",
              pdf_artifact_version_id: "pdf-1",
            }),
          ),
        ),
      ),
    );

    renderRoute(
      "/applications/app-1/draft",
      "/applications/:applicationId/draft",
      <DraftRenderPanel approvedRevisionId="revision-1" onQueued={vi.fn()} />,
    );

    expect(await screen.findByRole("link", { name: "מעבר לגרסה המוכנה" })).toHaveAttribute(
      "href",
      "/revisions/revision-1",
    );
    expect(screen.getByText("שלב הטיוטה הושלם.")).toBeInTheDocument();
  });
});
