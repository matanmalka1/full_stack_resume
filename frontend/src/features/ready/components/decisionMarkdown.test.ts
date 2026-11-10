import { describe, expect, it } from "vitest";

import { parseDecisionMarkdown, readDecision } from "./decisionMarkdown";

/* The template `export_decision_markdown` writes today (cv_engine/application/services/
   drafts/history.py). */
const record = `# CV Decision and Provenance

- Application: Acme — Backend Engineer
- Application ID: \`app-1\`
- Document ID: \`doc-1\`
- Document SHA-256: \`abc\`
- Preparation state: ready
- Approved at: 2026-11-01T10:00:00Z

## Classification

- Track: development
- Profile: backend
- Emphasis: technical
- Language: he
- Fit: strong

- User overrides: {}

## Facts the content uses

- \`fact.one\`
- \`fact.two\`

## Facts the document depends on

- \`fact.one\`: canonical
- \`fact.two\`: pending

## Content report

- Content check: failed
- Passed: False
- style/LONG_LINE: Line is too long

## Exact lineage

- Job text SHA-256: \`def\`
- Job analysis ID: \`an-1\`
- Built with Profile version: \`v1\`
`;

describe("readDecision", () => {
  it("reads the parts of the current template", () => {
    const reading = readDecision(parseDecisionMarkdown(record));

    expect(reading.application).toBe("Acme — Backend Engineer");
    expect(reading.preparationState).toBe("ready");
    expect(reading.approvedAt).toBe("2026-11-01T10:00:00Z");
    expect(reading.classification.map((pair) => pair.key)).toEqual(["Track", "Profile", "Emphasis", "Language", "Fit"]);
    expect(reading.language).toBe("he");
    expect(reading.overrides).toBe("");
    expect(reading.factIds).toEqual(["fact.one", "fact.two"]);
    expect(reading.contentCheck).toBe("failed");
    expect(reading.contentIssues).toEqual([{ key: "style/LONG_LINE", value: "Line is too long" }]);
  });

  it("leaves out what the record does not say", () => {
    const reading = readDecision(
      parseDecisionMarkdown(
        "# CV Decision and Provenance\n\n- Approved at: \n\n## Facts the content uses\n\n- None recorded\n",
      ),
    );

    expect(reading.approvedAt).toBeNull();
    expect(reading.overrides).toBeNull();
    expect(reading.factIds).toEqual([]);
    expect(reading.contentCheck).toBeNull();
  });
});
