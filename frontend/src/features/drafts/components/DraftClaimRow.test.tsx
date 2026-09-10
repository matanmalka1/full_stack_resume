import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { DraftClaim, DraftFact } from "@/api/contracts";
import { DraftClaimRow } from "./DraftClaimRow";
import type { DraftClaimActions } from "../model/drafts.types";

/* The one behavior in question: editing a line disconnects it from its canonical fact,
   and until now nothing on screen said so or offered a way back. */

const claim: DraftClaim = {
  claim_id: "claim-1",
  claim_type: "canonical",
  fact_ids: ["fact-1"],
  style: "paragraph",
  text: "מפתח/ת Full-Stack עם חמש שנות ניסיון.",
};

const facts: DraftFact[] = [{ fact_id: "fact-1", linked_claim_ids: ["claim-1"], text: "חמש שנות ניסיון" }];

const actions = (overrides: Partial<DraftClaimActions> = {}): DraftClaimActions => ({
  onCommit: vi.fn(),
  onEdit: vi.fn(),
  onRegenerate: vi.fn(),
  onRemove: vi.fn(),
  regenerationDisabled: false,
  ...overrides,
});

const openEditor = () => fireEvent.click(screen.getByRole("button", { name: "עריכת השורה" }));

describe("DraftClaimRow", () => {
  it("shows no disconnect warning before the text changes", () => {
    render(<DraftClaimRow actions={actions()} claim={claim} facts={facts} removal={{ route: "none" }} />);
    openEditor();
    expect(screen.queryByText("השורה מנותקת מהעובדה הקנונית")).not.toBeInTheDocument();
  });

  it("warns once the typed text diverges from the line the edit opened with", () => {
    render(<DraftClaimRow actions={actions()} claim={claim} facts={facts} removal={{ route: "none" }} />);
    openEditor();
    fireEvent.change(screen.getByRole("textbox", { name: "טקסט השורה" }), { target: { value: "ניסוח חדש" } });
    expect(screen.getByText("השורה מנותקת מהעובדה הקנונית")).toBeInTheDocument();
  });

  it("reverts to the original text and commits it, rather than a re-derived value", () => {
    const rowActions = actions();
    render(<DraftClaimRow actions={rowActions} claim={claim} facts={facts} removal={{ route: "none" }} />);
    openEditor();
    const textbox = screen.getByRole("textbox", { name: "טקסט השורה" });
    fireEvent.change(textbox, { target: { value: "ניסוח חדש" } });

    fireEvent.click(screen.getByRole("button", { name: "שחזור הטקסט הקודם" }));

    expect(textbox).toHaveValue(claim.text);
    expect(rowActions.onEdit).toHaveBeenLastCalledWith(claim, claim.text);
    expect(rowActions.onCommit).toHaveBeenCalled();
    expect(screen.queryByText("השורה מנותקת מהעובדה הקנונית")).not.toBeInTheDocument();
  });
});
