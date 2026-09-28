import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiProblem, type ProblemDetails } from "@/api/client";
import { ErrorCallout } from "./ErrorCallout";

const problem = (overrides: Partial<ProblemDetails> = {}): ApiProblem =>
  new ApiProblem({
    type: "about:blank#unknown_record",
    title: "Not Found",
    status: 404,
    code: "UNKNOWN_RECORD",
    detail: "unknown application: 00000000-0000-0000-0000-000000000000",
    ...overrides,
  });

describe("ErrorCallout", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("titles the failure in the screen's words and explains a known code in Hebrew", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    render(<ErrorCallout error={problem()} title="לא ניתן לטעון את המועמדות" />);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("לא ניתן לטעון את המועמדות");
    expect(alert).toHaveTextContent("הפריט המבוקש לא נמצא. ייתכן שנמחק. אפשר לרענן את העמוד ולנסות שוב.");
    expect(screen.queryByText(/Not Found|unknown application|UNKNOWN_RECORD/)).not.toBeInTheDocument();
  });

  it("keeps server prose for an unknown code in the log, not on the page", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    render(
      <ErrorCallout
        error={problem({ code: "FUTURE_PROBLEM", detail: "Safe future explanation.", status: 412 })}
        fallbackDetail="הרשומות לא השתנו. אפשר לנסות שוב."
        title="ההגשה לא נרשמה"
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("ההגשה לא נרשמה");
    expect(screen.getByRole("alert")).toHaveTextContent("הרשומות לא השתנו. אפשר לנסות שוב.");
    expect(screen.queryByText(/Safe future explanation/)).not.toBeInTheDocument();
    expect(warn).toHaveBeenCalledWith(
      "ui_error",
      expect.objectContaining({ code: "FUTURE_PROBLEM", detail: "Safe future explanation.", status: 412 }),
    );
  });

  it("never renders a local exception's text", () => {
    const logged = vi.spyOn(console, "error").mockImplementation(() => {});
    render(<ErrorCallout error={new Error("Settings require a current ETag")} title="ההגדרות לא נשמרו" />);

    expect(screen.getByRole("alert")).toHaveTextContent("הפעולה לא הושלמה. אפשר לרענן את העמוד ולנסות שוב.");
    expect(screen.queryByText(/ETag/)).not.toBeInTheDocument();
    expect(logged).toHaveBeenCalledWith(
      "ui_error",
      expect.objectContaining({ message: "Settings require a current ETag" }),
    );
  });

  it("lists field refusals the form could not place, and leaves out the ones it did", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const refused = problem({
      code: "REQUEST_VALIDATION_FAILED",
      status: 422,
      context: {
        issues: [
          { location: ["body", "job_text"], type: "string_too_short" },
          { location: ["body", "source_url"], type: "string_too_long" },
        ],
      },
    });
    const { rerender } = render(<ErrorCallout error={refused} title="לא ניתן לשמור" />);

    expect(screen.getByText("טקסט המשרה: יש למלא את השדה.")).toBeInTheDocument();
    expect(screen.getByText("כתובת המשרה: הערך ארוך מדי.")).toBeInTheDocument();

    rerender(<ErrorCallout error={refused} inlineFields={new Set(["job_text"])} title="לא ניתן לשמור" />);

    expect(screen.queryByText("טקסט המשרה: יש למלא את השדה.")).not.toBeInTheDocument();
    expect(screen.getByText("כתובת המשרה: הערך ארוך מדי.")).toBeInTheDocument();

    rerender(<ErrorCallout error={refused} inlineFields={new Set(["job_text", "source_url"])} title="לא ניתן לשמור" />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "חלק מהפרטים אינם תקינים. יש לתקן את השדות המסומנים ולנסות שוב.",
    );
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
  });
});
