import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { settingsQueryKey } from "@/api/settings";
import { HASH, cvDocument, settings } from "@/test/fixtures";
import { isEditable } from "../model/drafts.types";
import { DraftTemplateControl } from "./DraftTemplateControl";

const renderControl = (props: { onApply: (template: string | null) => Promise<void>; stamped?: boolean }) => {
  const client = new QueryClient();
  client.setQueryData(settingsQueryKey, { settings: settings(), etag: '"settings-0"' });
  const draft = cvDocument();
  if (!isEditable(draft)) throw new Error("fixture document has no outline");
  return render(
    <QueryClientProvider client={client}>
      <DraftTemplateControl disabled={false} draft={draft} onApply={props.onApply} stamped={props.stamped ?? false} />
    </QueryClientProvider>,
  );
};

describe("DraftTemplateControl", () => {
  it("previews the saved CV in every template and applies only the chosen one", async () => {
    const onApply = vi.fn(() => Promise.resolve());
    renderControl({ onApply });
    expect(screen.getAllByText("תבנית המסלול")[0]).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "החלפת תבנית" }));
    const apply = screen.getByRole("button", { name: "החלת התבנית" });
    expect(apply).toBeDisabled();
    expect(screen.getByTitle("תצוגה מקדימה: LaTeX")).toHaveAttribute(
      "src",
      `/api/v1/applications/app-1/document/preview?template=latex&v=${HASH}`,
    );
    expect(screen.getByTitle("תצוגה מקדימה: תבנית המסלול").getAttribute("src")).toContain("template=track");
    expect(screen.queryByText("המסמך יחזור לטיוטה")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: /LaTeX/ }));
    fireEvent.click(apply);
    await waitFor(() => expect(onApply).toHaveBeenCalledWith("latex"));
  });

  it("warns that an approved CV returns to draft, and keeps the dialog open on failure", async () => {
    const onApply = vi.fn(() => Promise.reject(new Error("conflict")));
    renderControl({ onApply, stamped: true });
    fireEvent.click(screen.getByRole("button", { name: "החלפת תבנית" }));
    fireEvent.click(screen.getByRole("radio", { name: /Deedy/ }));
    expect(screen.getByText("המסמך יחזור לטיוטה")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "החלת התבנית" }));
    expect(await screen.findByText("לא ניתן להחליף תבנית")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "החלת התבנית" })).toBeInTheDocument();
  });
});
