import { render, screen } from "@testing-library/react";

import { Callout } from "./Callout";

describe("Callout", () => {
  it("presents informational content independently from progress", () => {
    render(<Callout title="הנתונים עודכנו" tone="info" />);

    expect(screen.getByText("מידע")).toBeInTheDocument();
    expect(screen.getByText("מידע")).toHaveClass("text-cv-info");
    expect(screen.getByText("הנתונים עודכנו").closest("div.rounded-control")).toHaveClass("bg-cv-info-soft/60");
  });
});
