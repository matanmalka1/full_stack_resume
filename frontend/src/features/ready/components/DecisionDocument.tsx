import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { type ReactNode, useMemo } from "react";

import type { Fact } from "@/api/contracts";
import { factsQueryOptions } from "@/api/facts";
import type { DecisionExport } from "@/api/contracts";
import { factLabelInLanguage, factSourceLabel } from "@/features/facts";
import { emphasisLabels, fitLevelLabel, languageLabels, profileLabels, trackLabel } from "@/features/preparation";
import { Button } from "@/ui/Button";
import { Disclosure } from "@/ui/Disclosure";
import { EmptyState } from "@/ui/EmptyState";
import { LiveRegion } from "@/ui/LiveRegion";
import { LtrText } from "@/ui/LtrText";
import { Skeleton } from "@/ui/Skeleton";
import { SummaryList, type SummaryItem } from "@/ui/SummaryList";
import {
  type DecisionBlock,
  type DecisionSection,
  parseDecisionMarkdown,
  parseInline,
  readDecision,
} from "./decisionMarkdown";

/* Rows of a list and spans of a line are positional: the document is immutable, so their
   order is the only identity they have. */
/* oxlint-disable react/no-array-index-key */

const Inline = ({ text }: { text: string }) => (
  <>
    {parseInline(text).map((span, index) => {
      switch (span.kind) {
        case "code":
          /* Identifiers and hashes are one unbroken run; they wrap anywhere rather than
             widen the aside. */
          return (
            <code className="mono-code break-all rounded-control bg-cv-surface-sunken px-1 text-caption" key={index}>
              {span.text}
            </code>
          );
        case "strong":
          return (
            <strong className="font-semibold text-cv-text" key={index}>
              {span.text}
            </strong>
          );
        case "link":
          return (
            <a
              className="text-cv-accent underline underline-offset-2"
              href={span.href}
              key={index}
              rel="noopener noreferrer"
              target="_blank"
            >
              {span.text}
            </a>
          );
        default:
          return span.text;
      }
    })}
  </>
);

const Block = ({ block }: { block: DecisionBlock }) => {
  switch (block.kind) {
    case "heading":
      return (
        <h6 className="font-medium text-cv-text" dir="auto">
          <Inline text={block.text} />
        </h6>
      );
    case "list":
      return (
        <ul className="flex list-disc flex-col gap-1 ps-5 marker:text-cv-text-muted">
          {block.items.map((item, index) => (
            <li dir="auto" key={index}>
              <Inline text={item} />
            </li>
          ))}
        </ul>
      );
    default:
      return (
        <p dir="auto">
          <Inline text={block.text} />
        </p>
      );
  }
};

/* A section the reading does not interpret, shown as the record wrote it. */
const RawSection = ({ section }: { section: DecisionSection }) => (
  <section className="flex flex-col gap-2">
    {section.heading === null ? null : (
      <h5 className="font-medium text-cv-text" dir="auto">
        <Inline text={section.heading} />
      </h5>
    )}
    <div className="flex flex-col gap-2 leading-6 text-cv-text-muted">
      {section.blocks.map((block, index) => (
        <Block block={block} key={index} />
      ))}
    </div>
  </section>
);

const Part = ({ children, title }: { children: ReactNode; title: string }) => (
  <section className="flex flex-col gap-3 border-t border-cv-border pt-4">
    <h4 className="font-semibold text-cv-text">{title}</h4>
    {children}
  </section>
);

/* The classification is written with the backend's English keys and values. Each key is
   named for a reader here, and each value through the same maps the analysis screens
   use, so "development-backend" reads the way it did when it was chosen. A key or value
   no map knows is shown as written. */
const byKey = (labels: Record<string, string>) => (value: string) => labels[value] ?? value;
const classificationTerms: Record<string, { label: (value: string) => string; term: string }> = {
  track: { term: "מסלול", label: trackLabel },
  profile: { term: "פרופיל", label: byKey(profileLabels) },
  emphasis: { term: "דגש", label: byKey(emphasisLabels) },
  language: { term: "שפת קורות החיים", label: byKey(languageLabels) },
  fit: { term: "התאמה למשרה", label: fitLevelLabel },
};

const classified = (key: string, value: string): { term: string; value: string } => {
  const known = classificationTerms[key.toLowerCase()];
  return known === undefined ? { term: key, value } : { term: known.term, value: known.label(value) };
};

/* Overrides are recorded as a JSON object over the same classification keys - what the
   user chose in place of the analysis - and read in the same words. Anything that is not
   such an object is shown as written. */
const overridesText = (raw: string): string => {
  try {
    const value: unknown = JSON.parse(raw);
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      return Object.entries(value)
        .map(([key, entry]) => {
          const item = classified(key, typeof entry === "string" ? entry : JSON.stringify(entry));
          return `${item.term}: ${item.value}`;
        })
        .join(" · ");
    }
  } catch {
    /* Not JSON: the text as written. */
  }
  return raw;
};

interface FactGroup {
  label: string;
  texts: string[];
}

/* Selected facts are recorded by id. A reader needs what each one says, so each id is
   resolved against the fact store and grouped by the file it lives in. The text is the
   fact's current wording, which may have moved since approval - the note above the list
   says so - and an id the store no longer holds is named as such rather than hidden. */
const groupFacts = (
  ids: string[],
  facts: Map<string, Fact>,
  language: string,
): { groups: FactGroup[]; missing: string[] } => {
  const groups = new Map<string, string[]>();
  const missing: string[] = [];
  for (const id of ids) {
    const fact = facts.get(id);
    if (fact === undefined) {
      missing.push(id);
      continue;
    }
    const label = factSourceLabel(fact.source);
    groups.set(label, [...(groups.get(label) ?? []), factLabelInLanguage(fact, language)]);
  }
  return { groups: [...groups].map(([label, texts]) => ({ label, texts })), missing };
};

const SelectedFacts = ({ ids, language }: { ids: string[]; language: string | null }) => {
  const factsQuery = useQuery({ ...factsQueryOptions(), enabled: ids.length > 0 });
  const facts = useMemo(
    () => new Map((factsQuery.data?.items ?? []).map((item) => [item.fact.fact_id, item.fact])),
    [factsQuery.data],
  );

  if (ids.length === 0) return <p className="text-cv-text-muted">לא נרשמו עובדות שנבחרו.</p>;
  if (factsQuery.error !== null) {
    return (
      <p className="text-cv-text-muted">
        לא ניתן לטעון כרגע את נוסח העובדות. נבחרו {ids.length} עובדות, והרשימה המלאה נשמרת בקובץ להורדה.
      </p>
    );
  }
  if (factsQuery.data === undefined) return <Skeleton className="block h-32 w-full" />;

  const { groups, missing } = groupFacts(ids, facts, language ?? "he");

  return (
    <div className="flex flex-col gap-4">
      <p className="text-caption text-cv-text-muted">מוצג הנוסח הנוכחי של כל עובדה במאגר.</p>
      {groups.map((group) => (
        <div className="flex flex-col gap-1.5" key={group.label}>
          <h5 className="text-caption font-semibold text-cv-text-muted">
            {group.label} · {group.texts.length}
          </h5>
          <ul className="flex list-disc flex-col gap-1 ps-5 leading-6 marker:text-cv-text-muted">
            {group.texts.map((text, index) => (
              <li dir="auto" key={index} lang={language ?? undefined}>
                {text}
              </li>
            ))}
          </ul>
        </div>
      ))}
      {missing.length === 0 ? null : (
        <div className="flex flex-col gap-1.5">
          <h5 className="text-caption font-semibold text-cv-text-muted">עובדות שאינן במאגר כעת · {missing.length}</h5>
          <ul className="flex flex-col gap-1">
            {missing.map((id) => (
              <li key={id}>
                <LtrText className="break-all text-caption text-cv-text-muted" mono>
                  {id}
                </LtrText>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

interface DecisionDocumentProps {
  decision: DecisionExport | undefined;
  onDownload: () => void;
  pending: boolean;
}

/* §16 `export_decision_markdown`: the provenance of the current document - its analysis,
   selection, the facts it depends on and its content report. It writes nothing, so this
   view offers reading and a download and nothing that edits it. */
export const DecisionDocument = ({ decision, onDownload, pending }: DecisionDocumentProps) => {
  /* A response without text content is a missing document, not a crash. */
  const content = typeof decision?.markdown === "string" ? decision.markdown : null;
  const parsed = useMemo(() => (content === null ? null : parseDecisionMarkdown(content)), [content]);

  if (pending) {
    return (
      <div className="flex flex-col gap-3">
        <LiveRegion>טוען את מסמך ההחלטה…</LiveRegion>
        <Skeleton className="block h-24 w-full" />
        <Skeleton className="block h-48 w-full" />
      </div>
    );
  }

  if (parsed === null || (parsed.title === null && parsed.sections.length === 0)) {
    return (
      <EmptyState className="text-support text-cv-text-muted">מסמך ההחלטה של המסמך הזה אינו זמין כרגע.</EmptyState>
    );
  }

  const reading = readDecision(parsed);
  const factCount = reading.selectedFactIds?.length ?? null;
  const overview: SummaryItem[] = [
    ...reading.classification.map(({ key, value }) => classified(key, value)),
    ...(factCount === null ? [] : [{ term: "עובדות שנבחרו", value: factCount === 0 ? "לא נרשמו" : String(factCount) }]),
    ...(reading.overrides === null
      ? []
      : [{ term: "בחירות ידניות", value: reading.overrides === "" ? "אין" : overridesText(reading.overrides) }]),
  ];

  return (
    <article aria-labelledby="decision-document-title" className="flex flex-col gap-4 text-support text-cv-text">
      <header className="flex flex-col gap-2">
        <h3 className="font-semibold text-cv-text" id="decision-document-title">
          למה קורות החיים נראים כך
        </h3>
        {reading.summary === null ? null : (
          <p className="text-body leading-7 text-cv-text" dir="auto">
            <Inline text={reading.summary} />
          </p>
        )}
      </header>

      {overview.length === 0 ? null : (
        <section aria-label="תקציר ההחלטה" className="rounded-control border border-cv-border bg-cv-surface-sunken p-3">
          <SummaryList items={overview} />
        </section>
      )}

      {reading.selectedFactIds === null ? null : (
        <Part title="העובדות שנבחרו לקורות החיים">
          <SelectedFacts ids={reading.selectedFactIds} language={reading.language} />
        </Part>
      )}

      {/* Record ids, content hashes and the approval actor: evidence for an audit, not
          reading for a person, so held closed and shown exactly as written. */}
      {reading.rest.length === 0 ? null : (
        <div className="border-t border-cv-border pt-4">
          <Disclosure summary="שרשרת המקור והאישור">
            <p className="mb-3">מזהי הרשומות וחתימות התוכן שהמסמך נבנה מהם, ומי אישר אותו.</p>
            <div className="flex flex-col gap-4">
              {reading.rest.map((section, index) => (
                <RawSection key={index} section={section} />
              ))}
            </div>
          </Disclosure>
        </div>
      )}

      <footer className="flex flex-col gap-2 border-t border-cv-border pt-4">
        <Button className="self-start" onClick={onDownload} variant="secondary">
          <Download aria-hidden="true" className="size-icon-md" />
          הורדת מסמך ההחלטה
        </Button>
        <p className="text-caption text-cv-text-muted">הקובץ כפי שהשרת מפיק אותו מהמסמך הנוכחי.</p>
      </footer>
    </article>
  );
};
