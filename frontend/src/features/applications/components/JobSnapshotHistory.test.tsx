import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { JobSnapshotHistory as History } from "@/api/contracts";
import { JobSnapshotHistory } from "./JobSnapshotHistory";

const item = (
  id: string,
  version: number,
  text: string | null,
  url = "https://jobs.example/one",
): History["items"][number] => ({
  id,
  version_number: version,
  captured_at: "2026-09-14T10:00:00Z",
  source_url: url,
  job_text: text,
});
const mount = (items: History["items"]) => {
  const fetch = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ active_job_snapshot_id: items.at(-1)?.id, items }), {
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <JobSnapshotHistory applicationId="app" activeSnapshotId={items.at(-1)?.id ?? "missing"} />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByText("היסטוריית נוסחי משרה"));
  return fetch;
};
afterEach(() => vi.unstubAllGlobals());

it("reads the single saved posting as text, without interpreting HTML", async () => {
  const fetch = mount([item("one", 1, "עברית <script>unsafe()</script> English")]);
  await screen.findByText(/קיים נוסח שמור אחד בלבד/);
  expect(document.querySelector("script")).toBeNull();
  expect(document.querySelector("pre")?.textContent).toBe("עברית <script>unsafe()</script> English");
  expect(fetch.mock.calls[0]?.[0]).toBe("/api/v1/applications/app/job-snapshots");
});

it("defaults to the last pair and permits any explicit pair without changing the active source", async () => {
  const fetch = mount([
    item("one", 1, "ישן"),
    item("two", 2, "עברית  English\n"),
    item("three", 3, "עברית English\n\n"),
  ]);
  const before = await screen.findByLabelText("לפני");
  const after = screen.getByLabelText("אחרי");
  expect(before).toHaveValue("two");
  expect(after).toHaveValue("three");
  expect(screen.getAllByRole("option", { name: /פעילה/ })).toHaveLength(2);
  fireEvent.click(screen.getByText("הצגת רווחים ושבירות שורה באזור שהשתנה"));
  expect(screen.getByText(/· = רווח/)).toBeInTheDocument();
  fireEvent.change(before, { target: { value: "one" } });
  fireEvent.change(after, { target: { value: "two" } });
  expect(document.querySelectorAll("pre")[0]?.textContent).toBe("ישן");
  expect(document.querySelectorAll("pre")[1]?.textContent).toBe("עברית  English\n");
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("distinguishes a URL-only change from identical saved text", async () => {
  mount([item("one", 1, "same"), item("two", 2, "same", "https://jobs.example/two")]);
  expect(await screen.findByText("נוסח המשרה זהה בדיוק.")).toBeInTheDocument();
  expect(screen.getByText("כתובת המקור השתנתה.")).toBeInTheDocument();
});

it("shows unavailable content without reconstructing it and retains large readable text", async () => {
  const large = "עברית English\n".repeat(10000);
  mount([item("one", 1, null), item("two", 2, large)]);
  await screen.findByText("תוכן שמור חסר; לא ניתן להשוות את הנוסחים.");
  expect(document.querySelector("pre")?.textContent).toBe(large);
  expect(document.querySelector("pre")).toHaveAttribute("dir", "auto");
});

it("offers explicit retry after a history load failure", async () => {
  const fetch = vi
    .fn()
    .mockRejectedValueOnce(new TypeError("offline"))
    .mockResolvedValue(
      new Response(JSON.stringify({ active_job_snapshot_id: "one", items: [item("one", 1, "saved")] }), {
        headers: { "Content-Type": "application/json" },
      }),
    );
  vi.stubGlobal("fetch", fetch);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <JobSnapshotHistory applicationId="app" activeSnapshotId="one" />
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByText("היסטוריית נוסחי משרה"));
  fireEvent.click(await screen.findByRole("button", { name: "ניסיון חוזר" }));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  expect(await screen.findByText(/קיים נוסח שמור אחד בלבד/)).toBeInTheDocument();
});
