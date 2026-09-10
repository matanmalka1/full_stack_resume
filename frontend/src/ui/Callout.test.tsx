import { render, screen } from "@testing-library/react";

import { Callout } from "./Callout";

describe("Callout", () => {
  it("presents informational content independently from progress", () => {
    render(<Callout title="הנתונים עודכנו" tone="info" />);

    expect(screen.getByText("מידע")).toBeInTheDocument();
    expect(screen.getByText("מידע")).toHaveClass("text-cv-info");
    const callout = screen.getByText("הנתונים עודכנו").closest("div.border-s-2");
    expect(callout).toHaveClass("border-s-cv-info");
    expect(callout).not.toHaveClass("bg-cv-info-soft/60");
  });
});
