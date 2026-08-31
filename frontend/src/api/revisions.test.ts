import { QueryClient } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { decisionMarkdownQueryOptions } from "./revisions";

afterEach(() => vi.unstubAllGlobals());

describe("decision Markdown export", () => {
  it("binds the revision to its application and uses the suggested safe filename", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          application_id: "app-1",
          approved_revision_id: "revision-1",
          content: "# Decision",
          content_hash: "hash-1",
        }),
        {
          headers: {
            "Content-Type": "application/json",
            "Content-Disposition": "attachment; filename*=UTF-8''Acme%20decision.md",
          },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient();

    const result = await client.fetchQuery(decisionMarkdownQueryOptions("revision-1", "app-1"));

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/approved-revisions/revision-1/decision-markdown?application_id=app-1",
    );
    expect(result).toMatchObject({ content: "# Decision", filename: "Acme decision.md" });
  });
});
