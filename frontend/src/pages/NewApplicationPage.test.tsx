import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DuplicateMatch } from "../api/contracts";
import { NewApplicationPage } from "./NewApplicationPage";

const jsonResponse = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const problemResponse = (
  status: number,
  code: string,
  detail: string,
  context?: Record<string, unknown>,
): Response =>
  new Response(
    JSON.stringify({
      type: `about:blank#${code.toLowerCase()}`,
      title: "Precondition Failed",
      status,
      code,
      detail,
      ...(context === undefined ? {} : { context }),
    }),
    { status, headers: { "Content-Type": "application/problem+json" } },
  );

interface Call {
  path: string;
  body: unknown;
}

/* One stub for both intake endpoints, recording what each one was actually sent: the
   acknowledgement and the exact job text are the contract this screen has to keep. */
const stubFetch = (responses: Record<string, Response[]>) => {
  const calls: Call[] = [];
  const remaining = new Map(Object.entries(responses).map(([path, list]) => [path, [...list]]));

  const fetchMock = vi.fn((input: RequestInfo | URL, init: RequestInit = {}) => {
    const path = String(input);
    calls.push({
      path,
      body: typeof init.body === "string" ? JSON.parse(init.body) : undefined,
    });

    const next = remaining.get(path)?.shift();

    if (next === undefined) {
      throw new Error(`unexpected request to ${path}`);
    }

    return Promise.resolve(next);
  });

  vi.stubGlobal("fetch", fetchMock);

  return calls;
};

const match = (overrides: Partial<DuplicateMatch> = {}): DuplicateMatch => ({
  application_id: "app-existing",
  company: "Acme",
  target_role: "Backend Engineer",
  matched_on: ["company_title"],
  ...overrides,
});

const DUPLICATE_CHECK_PATH = "/api/v1/applications/duplicate-check";
const CREATE_PATH = "/api/v1/applications";

const renderPage = () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route element={<NewApplicationPage />} path="/" />
          {/* One destination for both outcomes: a newly created Application and one
              opened from a duplicate reach the same context screen. */}
          <Route element={<h1>מועמדות קיימת</h1>} path="/applications/:applicationId" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

const fillIntake = (jobText = "Job description text") => {
  fireEvent.change(screen.getByLabelText("שם החברה"), { target: { value: " Acme " } });
  fireEvent.change(screen.getByLabelText("תפקיד היעד"), {
    target: { value: "Backend Engineer" },
  });
  fireEvent.change(screen.getByLabelText("טקסט המשרה"), { target: { value: jobText } });
};

const chooseFile = (file: File) => {
  const input = screen.getByLabelText("קריאת קובץ טקסט מהמחשב (לא חובה)");

  /* jsdom keeps `files` read-only, so the selection is defined rather than assigned
     through the event, which would silently do nothing. */
  Object.defineProperty(input, "files", { configurable: true, value: [file] });
  fireEvent.change(input);
};

const submitForm = () => {
  fireEvent.click(screen.getByRole("button", { name: "יצירת מועמדות" }));
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("NewApplicationPage", () => {
  it("labels every intake field in Hebrew and keeps the source URL an LTR island", () => {
    renderPage();

    expect(screen.getByRole("heading", { level: 1, name: "משרה חדשה" })).toBeInTheDocument();
    expect(screen.getByLabelText("שם החברה")).toBeInTheDocument();
    expect(screen.getByLabelText("תפקיד היעד")).toBeInTheDocument();
    expect(screen.getByLabelText("טקסט המשרה")).toHaveAttribute("dir", "auto");
    expect(screen.getByLabelText("כתובת המשרה (לא חובה)")).toHaveAttribute("dir", "ltr");
    expect(
      screen.getByText("הכתובת נשמרת כתיעוד מקור בלבד. המערכת אינה פותחת אותה ואינה מייבאת ממנה טקסט."),
    ).toBeInTheDocument();
  });

  it("reads a chosen .txt file into the job text area without sending it anywhere", async () => {
    const calls = stubFetch({});
    renderPage();

    chooseFile(new File(["Senior Backend Engineer\nTel Aviv"], "job.txt", { type: "text/plain" }));

    await waitFor(() => {
      expect(screen.getByLabelText("טקסט המשרה")).toHaveValue(
        "Senior Backend Engineer\nTel Aviv",
      );
    });
    expect(screen.getByRole("status")).toHaveTextContent("job.txt");
    expect(calls).toEqual([]);
  });

  it("refuses a file that is not a text file and leaves the job text untouched", async () => {
    renderPage();

    chooseFile(new File(["%PDF-1.7"], "job.pdf", { type: "application/pdf" }));

    expect(await screen.findByText("ניתן לבחור קובץ טקסט בלבד, עם סיומת txt.")).toBeInTheDocument();
    expect(screen.getByLabelText("טקסט המשרה")).toHaveValue("");
  });

  it("creates the application directly when the precheck finds nothing", async () => {
    const calls = stubFetch({
      [DUPLICATE_CHECK_PATH]: [jsonResponse({ matches: [] })],
      [CREATE_PATH]: [
        jsonResponse(
          {
            application_id: "app-new",
            job_snapshot_id: "snap-1",
            warnings: [],
            duplicate_matches: [],
          },
          201,
        ),
      ],
    });
    renderPage();

    fillIntake();
    submitForm();

    expect(await screen.findByRole("heading", { name: "מועמדות קיימת" })).toBeInTheDocument();
    expect(calls).toEqual([
      {
        path: DUPLICATE_CHECK_PATH,
        body: {
          company: "Acme",
          target_role: "Backend Engineer",
          job_text: "Job description text",
          source_url: null,
        },
      },
      {
        path: CREATE_PATH,
        body: {
          company: "Acme",
          target_role: "Backend Engineer",
          job_text: "Job description text",
          source_url: null,
          acknowledged_duplicates: false,
        },
      },
    ]);
  });

  it("offers the existing application and an explicit override instead of creating", async () => {
    const calls = stubFetch({
      [DUPLICATE_CHECK_PATH]: [
        jsonResponse({ matches: [match({ matched_on: ["source_url", "company_title"] })] }),
      ],
    });
    renderPage();

    fillIntake();
    submitForm();

    expect(await screen.findByText("נמצאו מועמדויות דומות")).toBeInTheDocument();
    expect(screen.getByText("אותה כתובת מקור · אותה חברה ואותו תפקיד")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "פתיחת המועמדות הקיימת" })).toHaveAttribute(
      "href",
      "/applications/app-existing",
    );
    expect(screen.getByRole("button", { name: "יצירה בכל זאת" })).toBeInTheDocument();
    expect(calls.map((call) => call.path)).toEqual([DUPLICATE_CHECK_PATH]);
  });

  it("creates anyway with an explicit acknowledgement and no second precheck", async () => {
    const calls = stubFetch({
      [DUPLICATE_CHECK_PATH]: [jsonResponse({ matches: [match()] })],
      [CREATE_PATH]: [
        jsonResponse(
          {
            application_id: "app-new",
            job_snapshot_id: "snap-1",
            warnings: ["DUPLICATE_COMPANY_TITLE"],
            duplicate_matches: [match()],
          },
          201,
        ),
      ],
    });
    renderPage();

    fillIntake();
    submitForm();

    fireEvent.click(await screen.findByRole("button", { name: "יצירה בכל זאת" }));

    expect(await screen.findByRole("heading", { name: "מועמדות קיימת" })).toBeInTheDocument();
    expect(calls.map((call) => call.path)).toEqual([DUPLICATE_CHECK_PATH, CREATE_PATH]);
    expect(calls[1].body).toMatchObject({ acknowledged_duplicates: true });
  });

  it("presents the create command's own duplicate refusal as the same choice", async () => {
    stubFetch({
      [DUPLICATE_CHECK_PATH]: [jsonResponse({ matches: [] })],
      [CREATE_PATH]: [
        problemResponse(
          412,
          "DUPLICATE_ACKNOWLEDGEMENT_REQUIRED",
          "possible duplicate applications require explicit acknowledgement",
          { matches: [match({ application_id: "app-raced" })] },
        ),
      ],
    });
    renderPage();

    fillIntake();
    submitForm();

    expect(await screen.findByText("נמצאו מועמדויות דומות")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "פתיחת המועמדות הקיימת" })).toHaveAttribute(
      "href",
      "/applications/app-raced",
    );
    expect(screen.queryByText("חסימה")).not.toBeInTheDocument();
  });

  /* The precheck is asynchronous and the form stays editable while it runs, so an answer
     can arrive describing text that is no longer on screen. Acting on it would send an
     acknowledgement for one posting together with the text of another. */
  it("does not apply a duplicate answer that arrives after the intake changed", async () => {
    let answer!: (response: Response) => void;
    const inFlight = new Promise<Response>((resolve) => {
      answer = resolve;
    });
    vi.stubGlobal("fetch", vi.fn(() => inFlight));

    renderPage();
    fillIntake();
    submitForm();

    fireEvent.change(screen.getByLabelText("טקסט המשרה"), {
      target: { value: "A completely different posting" },
    });
    answer(jsonResponse({ matches: [match()] }));

    expect(await screen.findByText("הקלט השתנה מאז הבדיקה")).toBeInTheDocument();
    expect(screen.queryByText("נמצאו מועמדויות דומות")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "יצירה בכל זאת" })).not.toBeInTheDocument();
  });

  it("clears the stale-answer notice once the intake is edited again", async () => {
    let answer!: (response: Response) => void;
    const inFlight = new Promise<Response>((resolve) => {
      answer = resolve;
    });
    vi.stubGlobal("fetch", vi.fn(() => inFlight));

    renderPage();
    fillIntake();
    submitForm();

    fireEvent.change(screen.getByLabelText("טקסט המשרה"), { target: { value: "Second text" } });
    answer(jsonResponse({ matches: [match()] }));

    expect(await screen.findByText("הקלט השתנה מאז הבדיקה")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("טקסט המשרה"), { target: { value: "Third text" } });

    await waitFor(() => {
      expect(screen.queryByText("הקלט השתנה מאז הבדיקה")).not.toBeInTheDocument();
    });
  });

  it("withdraws the duplicate choice when the intake is edited", async () => {
    stubFetch({
      [DUPLICATE_CHECK_PATH]: [jsonResponse({ matches: [match()] })],
    });
    renderPage();

    fillIntake();
    submitForm();

    expect(await screen.findByText("נמצאו מועמדויות דומות")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("טקסט המשרה"), {
      target: { value: "A different posting" },
    });

    await waitFor(() => {
      expect(screen.queryByText("נמצאו מועמדויות דומות")).not.toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "יצירה בכל זאת" })).not.toBeInTheDocument();
  });

  it("shows a refused creation as a blocker with the server's safe detail", async () => {
    stubFetch({
      [DUPLICATE_CHECK_PATH]: [jsonResponse({ matches: [] })],
      [CREATE_PATH]: [problemResponse(412, "PRECONDITION_FAILED", "job text is required")],
    });
    renderPage();

    fillIntake();
    submitForm();

    expect(await screen.findByText("job text is required")).toBeInTheDocument();
    expect(screen.getByText("חסימה")).toBeInTheDocument();
    /* The failure code is no longer shown. `detail` is the server's own sentence about
       the refusal and it is the body of the callout; the code beside it named the same
       refusal in a vocabulary the reader cannot act on. What this test guards is that a
       refusal is reported as a blocker carrying the server's safe detail - never the
       exception text, and never a message this screen invented. */
    expect(screen.queryByText(/PRECONDITION_FAILED/)).toBeNull();
  });

  it("refuses to submit an empty form and never calls the API", async () => {
    const calls = stubFetch({});
    renderPage();

    submitForm();

    expect(await screen.findByText("יש להזין את שם החברה.")).toBeInTheDocument();
    expect(screen.getByText("יש להזין את תפקיד היעד.")).toBeInTheDocument();
    expect(screen.getByText("יש להזין את טקסט המשרה.")).toBeInTheDocument();
    expect(calls).toEqual([]);
  });
});
