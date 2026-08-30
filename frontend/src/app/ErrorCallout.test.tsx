import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApiProblem } from "../api/client";
import { ErrorCallout } from "./ErrorCallout";

describe("ErrorCallout", () => {
  it("renders safe Problem Details and keeps the machine data secondary", () => {
    render(
      <ErrorCallout
        error={
          new ApiProblem({
            type: "about:blank#state_conflict",
            title: "Conflict",
            status: 409,
            code: "STATE_CONFLICT",
            detail: "The application changed.",
          })
        }
        fallbackDetail="fallback detail"
        fallbackTitle="fallback title"
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Conflict");
    expect(screen.getByRole("alert")).toHaveTextContent("The application changed.");
    expect(screen.getByText("STATE_CONFLICT · HTTP 409")).toBeInTheDocument();
    expect(screen.queryByText("fallback detail")).not.toBeInTheDocument();
  });

  it("never renders an unknown exception message", () => {
    render(
      <ErrorCallout
        error={new Error("private implementation detail")}
        fallbackDetail="אפשר לנסות שוב."
        fallbackTitle="הפעולה נכשלה"
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("אפשר לנסות שוב.");
    expect(screen.queryByText("private implementation detail")).not.toBeInTheDocument();
  });
});
