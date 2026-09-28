/* The decision document is Markdown the server writes from a fixed template: one `#`
   title, `##` sections, paragraphs and `-` lists with inline code. This reads exactly that
   subset into blocks React renders as elements - never as HTML - so nothing in the stored
   text can become markup. Anything outside the subset stays readable as a paragraph.

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

type InlineSpan = { kind: "code" | "strong" | "text"; text: string } | { kind: "link"; href: string; text: string };

/* Only http(s) targets become links; any other scheme stays visible text. */
const INLINE = /`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;

export const parseInline = (text: string): InlineSpan[] => {
  const spans: InlineSpan[] = [];
  let last = 0;
  for (const match of text.matchAll(INLINE)) {
    const start = match.index ?? 0;
    if (start > last) spans.push({ kind: "text", text: text.slice(last, start) });
    const [whole, code, strong, label, href] = match;
    if (code !== undefined) spans.push({ kind: "code", text: code });
    else if (strong !== undefined) spans.push({ kind: "strong", text: strong });
    else spans.push({ kind: "link", href: href!, text: label! });
    last = start + whole.length;
  }
  if (last < text.length) spans.push({ kind: "text", text: text.slice(last) });
  return spans;
};

/* The template's sections, read for a person rather than shown as written. The server
   names facts by id and the classification by English key; a reader wants the decision,
   what shaped it, and which facts it drew on. Each part is read off the section the
   template gives it, and a document without that section shows less rather than a
   guessed value. Everything the reading does not claim - lineage hashes, the approval
   actor, any section a later template adds - stays in `rest`, shown as written, so
   nothing in the record drops out of view. */
interface DecisionReading {
  classification: { key: string; value: string }[];
  language: string | null;
  /* `""` when the record says there were none; `null` when it does not say. */
  overrides: string | null;
  rest: DecisionSection[];
  selectedFactIds: string[] | null;
  summary: string | null;
}

const EMPTY_VALUES = new Set(["", "{}", "[]", "none", "null"]);
const READ_SECTIONS = new Set(["decision", "classification", "selected facts", "overrides"]);

const keyValue = (line: string) => {
  const match = /^([^:]+):\s*(.*)$/.exec(line);
  return match === null ? null : { key: match[1]!.trim(), value: match[2]!.trim() };
};

export const readDecision = (parsed: ParsedDecision): DecisionReading => {
  const section = (name: string) => parsed.sections.find((candidate) => candidate.heading?.toLowerCase() === name);
  const listItems = (name: string) =>
    section(name)?.blocks.flatMap((block) => (block.kind === "list" ? block.items : [])) ?? null;

  const summary =
    section("decision")
      ?.blocks.flatMap((block) => (block.kind === "paragraph" ? [block.text] : []))
      .join(" ") || null;

  const classification = (listItems("classification") ?? []).flatMap((line) => {
    const pair = keyValue(line);
    return pair === null || pair.value === "" ? [] : [pair];
  });
  const language = classification.find((pair) => pair.key.toLowerCase() === "language")?.value ?? null;

  const facts = listItems("selected facts");
  const selectedFactIds =
    facts === null
      ? null
      : facts.filter((fact) => !/^none recorded$/i.test(fact)).map((fact) => fact.replace(/^`|`$/g, "").trim());

  const overrideValue = (listItems("overrides") ?? [])
    .map(keyValue)
    .find((pair) => pair?.key.toLowerCase() === "user overrides")?.value;
  const overrides =
    overrideValue === undefined ? null : EMPTY_VALUES.has(overrideValue.toLowerCase()) ? "" : overrideValue;

  const rest = parsed.sections.filter(
    (candidate) => candidate.heading === null || !READ_SECTIONS.has(candidate.heading.toLowerCase()),
  );

  return { classification, language, overrides, rest, selectedFactIds, summary };
};
