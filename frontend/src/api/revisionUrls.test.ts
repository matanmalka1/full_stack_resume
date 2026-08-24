import { describe, expect, it } from "vitest";

import { approvedPreviewSrc, recruiterPdfHref } from "./revisions";

describe("approved artifact URLs", () => {
  it("encodes the approved revision in the path", () => {
    expect(approvedPreviewSrc("revision/1", "html-1")).toContain("/approved-revisions/revision%2F1/");
  });

  it("names the exact HTML artifact in the preview query", () => {
    expect(
      approvedPreviewSrc("revision-1", "html/1").endsWith(
        "html_artifact_version_id=html%2F1",
      ),
    ).toBe(true);
  });

  it("names the exact PDF artifact without resolving a latest version", () => {
    expect(recruiterPdfHref("revision-1", "pdf/1")).toBe("/api/v1/approved-revisions/revision-1/recruiter-pdf?pdf_artifact_version_id=pdf%2F1");
  });
});
