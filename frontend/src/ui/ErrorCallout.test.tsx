import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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
  it("uses the Hebrew message for a known problem code and hides server prose", () => {
    render(<ErrorCallout error={problem()} fallbackTitle="לא ניתן לטעון" />);

    expect(screen.getByRole("alert")).toHaveTextContent("הרשומה לא נמצאה");
    expect(screen.getByRole("alert")).toHaveTextContent("הפריט המבוקש אינו קיים או שכבר אינו זמין.");
    expect(screen.queryByText(/Not Found|unknown application/)).not.toBeInTheDocument();
  });

  it("uses safe server detail only for an unknown code", () => {
    render(
      <ErrorCallout
        error={problem({ code: "FUTURE_PROBLEM", detail: "Safe future explanation." })}
        fallbackTitle="לא ניתן לטעון"
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("הבקשה נכשלה");
    expect(screen.getByRole("alert")).toHaveTextContent("Safe future explanation.");
  });

  it("presents request issues as field errors", () => {
    render(
      <ErrorCallout
        error={problem({
          code: "REQUEST_VALIDATION_FAILED",
          context: { issues: [{ location: ["body", "job_text"], type: "string_too_short" }] },
        })}
        fallbackTitle="לא ניתן לשמור"
      />,
    );

    expect(screen.getByText("תיאור המשרה: הערך אינו תקין.")).toBeInTheDocument();
  });
});
