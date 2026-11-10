/* The decision document is Markdown the server writes from a fixed template: one `#`
   title, `##` sections, paragraphs and `-` lists with inline code. This reads exactly that
   subset into blocks - plain strings, never HTML - so nothing in the stored text can
   become markup. Anything outside the subset stays readable as a paragraph.

   Nothing here changes the stored content; the download still hands over the original. */

export type DecisionBlock =
  { kind: "heading"; text: string } | { kind: "list"; items: string[] } | { kind: "paragraph"; text: string };

export interface DecisionSection {
  blocks: DecisionBlock[];
  heading: string | null;
}

interface ParsedDecision {
  sections: DecisionSection[];
  title: string | null;
}

export const parseDecisionMarkdown = (content: string): ParsedDecision => {
  let title: string | null = null;
  const sections: DecisionSection[] = [{ blocks: [], heading: null }];
  let paragraph: string[] = [];
  let list: string[] | null = null;

  const current = () => sections[sections.length - 1]!;
  const flush = () => {
    if (paragraph.length > 0) current().blocks.push({ kind: "paragraph", text: paragraph.join(" ") });
    if (list !== null) current().blocks.push({ kind: "list", items: list });
    paragraph = [];
    list = null;
  };

  for (const raw of content.split(/\r?\n/)) {
    const line = raw.trim();
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    const item = /^[-*+]\s+(.*)$/.exec(line);

    if (line === "") {
      flush();
    } else if (heading !== null) {
      flush();
      const level = heading[1]!.length;
      const text = heading[2]!;
      if (level === 1 && title === null) title = text;
      else if (level <= 2) sections.push({ blocks: [], heading: text });
      else current().blocks.push({ kind: "heading", text });
    } else if (item !== null) {
      if (paragraph.length > 0) flush();
      (list ??= []).push(item[1]!);
    } else {
      if (list !== null) flush();
      paragraph.push(line);
    }
  }
  flush();

  return { sections: sections.filter((section) => section.heading !== null || section.blocks.length > 0), title };
};

/* The template's sections, read for a person rather than shown as written. The server
   names facts by id and the classification by English key; a reader wants which role the
   CV was built for, what shaped it, which facts it drew on and whether its content
   passed. Each part is read off the section the template gives it, and a document
   without that section shows less rather than a guessed value. Record ids, hashes and
   the lineage section are audit evidence, not reading: they stay in the downloaded file
   and are not shown. */
export interface DecisionPair {
  key: string;
  value: string;
}

export interface DecisionReading {
  /* "Company — Role", as the opening list names the Application. */
  application: string | null;
  approvedAt: string | null;
  classification: DecisionPair[];
  contentCheck: string | null;
  /* `group/code: message` lines of the content report. */
  contentIssues: DecisionPair[];
  /* The facts the content uses; `null` when the record has no such section. */
  factIds: string[] | null;
  language: string | null;
  /* `""` when the record says there were none; `null` when it does not say. */
  overrides: string | null;
  preparationState: string | null;
}

const EMPTY_VALUES = new Set(["", "{}", "[]", "none", "null"]);
const REPORT_READ = new Set(["content check", "passed"]);

const unquote = (value: string) => value.replace(/^`|`$/g, "").trim();

const keyValue = (line: string): DecisionPair | null => {
  const match = /^([^:]+):\s*(.*)$/.exec(line);
  return match === null ? null : { key: match[1]!.trim(), value: unquote(match[2]!.trim()) };
};

export const readDecision = (parsed: ParsedDecision): DecisionReading => {
  const listOf = (candidate: DecisionSection | undefined) =>
    candidate?.blocks.flatMap((block) => (block.kind === "list" ? block.items : [])) ?? null;
  const section = (name: string) =>
    listOf(parsed.sections.find((candidate) => candidate.heading?.toLowerCase() === name));
  const pairs = (items: string[] | null) =>
    (items ?? []).flatMap((line) => {
      const pair = keyValue(line);
      return pair === null ? [] : [pair];
    });
  const find = (from: DecisionPair[], key: string) =>
    from.find((pair) => pair.key.toLowerCase() === key)?.value || null;

  const preamble = pairs(listOf(parsed.sections.find((candidate) => candidate.heading === null)));

  const classified = pairs(section("classification"));
  const overrideValue = classified.find((pair) => pair.key.toLowerCase() === "user overrides")?.value;
  const overrides =
    overrideValue === undefined ? null : EMPTY_VALUES.has(overrideValue.toLowerCase()) ? "" : overrideValue;
  const classification = classified.filter((pair) => pair.value !== "" && pair.key.toLowerCase() !== "user overrides");

  const used = section("facts the content uses");
  const factIds =
    used === null ? null : used.filter((fact) => !/^none recorded$/i.test(fact)).map((fact) => unquote(fact));

  const report = pairs(section("content report"));

  return {
    application: find(preamble, "application"),
    approvedAt: find(preamble, "approved at"),
    classification,
    contentCheck: find(report, "content check"),
    contentIssues: report.filter((pair) => !REPORT_READ.has(pair.key.toLowerCase())),
    factIds,
    language: find(classification, "language"),
    overrides,
    preparationState: find(preamble, "preparation state"),
  };
};
