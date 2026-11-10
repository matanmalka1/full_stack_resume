import { useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { type ReactNode, useMemo } from "react";

import type { DecisionExport, Fact, PreparationState } from "@/api/contracts";
import { factsQueryOptions } from "@/api/facts";
import { factLabelInLanguage, factSourceLabel, factStatusLabel } from "@/features/facts";
import {
  classificationFieldLabels,
  emphasisLabels,
  fitLevelLabel,
  languageLabels,
  preparationStateLabels,
  profileLabels,
  trackLabel,
} from "@/features/preparation";
import { Button } from "@/ui/Button";
import { DateTime } from "@/ui/DateTime";
import { EmptyState } from "@/ui/EmptyState";
import { LiveRegion } from "@/ui/LiveRegion";
import { LtrText } from "@/ui/LtrText";
import { Skeleton } from "@/ui/Skeleton";
import { StatusBadge } from "@/ui/StatusBadge";
import type { Tone } from "@/ui/tone";
import { type DecisionPair, parseDecisionMarkdown, readDecision } from "./decisionMarkdown";

/* One part of the explanation: a numbered heading, a sentence saying what the part
   answers, and its content. The number is the reading order on a phone, where the parts
   stack; it is decoration, so the heading's text alone names the part. */
const Part = ({
  children,
  count,
  intro,
  step,
  title,
}: {
  children: ReactNode;
  count?: number;
  intro: string;
  step: number;
  title: string;
}) => (
  <section aria-labelledby={`decision-part-${step}`} className="flex flex-col gap-3">
    <div className="flex items-start gap-3">
      <span
        aria-hidden="true"
        className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-pill bg-cv-accent text-caption font-bold text-cv-on-accent"
      >
        {step}
      </span>
      <div className="flex min-w-0 flex-col gap-0.5">
        <h4
          className="flex flex-wrap items-center gap-2 text-heading-sm font-semibold text-cv-text"
          id={`decision-part-${step}`}
        >
          {title}
          {count === undefined ? null : (
            <span className="rounded-pill bg-cv-surface-muted px-2 text-caption font-bold text-cv-text-muted">
              {count}
            </span>
          )}
        </h4>
        <p className="text-support text-cv-text-muted">{intro}</p>
      </div>
    </div>
    <div className="sm:ps-9">{children}</div>
  </section>
);

/* The classification is written with the backend's English keys and values. Each key is
   named for a reader here, and each value through the same maps the analysis screens
   use, so "development-backend" reads the way it did when it was chosen. A key or value
   no map knows is shown as written. */
const byKey = (labels: Record<string, string>) => (value: string) => labels[value] ?? value;
const classificationTerms: Record<string, { label: (value: string) => string; term: string }> = {
  track: { term: classificationFieldLabels.track, label: trackLabel },
  profile: { term: classificationFieldLabels.profile, label: byKey(profileLabels) },
  emphasis: { term: classificationFieldLabels.emphasis, label: byKey(emphasisLabels) },
  language: { term: classificationFieldLabels.language, label: byKey(languageLabels) },
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
  facts: { id: string; status: Fact["status"]; text: string }[];
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
  const groups = new Map<string, FactGroup["facts"]>();
  const missing: string[] = [];
  for (const id of ids) {
    const fact = facts.get(id);
    if (fact === undefined) {
      missing.push(id);
      continue;
    }
    const label = factSourceLabel(fact.source);
    groups.set(label, [
      ...(groups.get(label) ?? []),
      { id, status: fact.status, text: factLabelInLanguage(fact, language) },
    ]);
  }
  return { groups: [...groups].map(([label, members]) => ({ label, facts: members })), missing };
};

const factStatusTones: Partial<Record<Fact["status"], Tone>> = { pending: "warning", deleted: "blocker" };

const SelectedFacts = ({ ids, language }: { ids: string[]; language: string | null }) => {
  const factsQuery = useQuery({ ...factsQueryOptions(), enabled: ids.length > 0 });
  const facts = useMemo(
    () => new Map((factsQuery.data?.items ?? []).map((item) => [item.fact.fact_id, item.fact])),
    [factsQuery.data],
  );

  if (ids.length === 0) return <p className="text-support text-cv-text-muted">לא נרשמו עובדות שנבחרו.</p>;
  if (factsQuery.error !== null) {
    return (
      <p className="text-support text-cv-text-muted">
        לא ניתן לטעון כרגע את נוסח העובדות. נבחרו {ids.length} עובדות, והרשימה המלאה נשמרת בקובץ להורדה.
      </p>
    );
  }
  if (factsQuery.data === undefined) return <Skeleton className="block h-32 w-full" />;

  const { groups, missing } = groupFacts(ids, facts, language ?? "he");

  return (
    <div className="flex flex-col gap-3">
      {groups.map((group) => (
        <div className="overflow-hidden rounded-surface border border-cv-border bg-cv-surface" key={group.label}>
          <h5 className="flex items-center justify-between gap-2 border-b border-cv-border bg-cv-surface-sunken px-4 py-2 text-caption font-semibold text-cv-text-muted">
            <span>{group.label}</span>
            <span>{group.facts.length}</span>
          </h5>
          <ul className="divide-y divide-cv-border">
            {group.facts.map((fact) => {
              const tone = factStatusTones[fact.status];
              return (
                <li
                  className="flex flex-col gap-1.5 px-4 py-2.5 sm:flex-row sm:items-start sm:justify-between sm:gap-4"
                  key={fact.id}
                >
                  <span
                    className="min-w-0 break-words text-support leading-6 text-cv-text"
                    dir="auto"
                    lang={language ?? undefined}
                  >
                    {fact.text}
                  </span>
                  {tone === undefined ? null : (
                    <StatusBadge className="self-start" tone={tone}>
                      {factStatusLabel(fact.status)}
                    </StatusBadge>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {missing.length === 0 ? null : (
        <div className="rounded-surface border border-dashed border-cv-border-strong px-4 py-3">
          <h5 className="mb-1.5 text-caption font-semibold text-cv-text-muted">
            עובדות שאינן במאגר כעת · {missing.length}
          </h5>
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
      <p className="text-caption text-cv-text-muted">מוצג הנוסח הנוכחי של כל עובדה במאגר.</p>
    </div>
  );
};

const contentChecks: Record<string, { label: string; tone: Tone }> = {
  passed: { label: "הבדיקה עברה", tone: "success" },
  failed: { label: "הבדיקה נכשלה", tone: "blocker" },
  outdated: { label: "הבדיקה אינה עדכנית", tone: "warning" },
  none: { label: "התוכן לא נבדק", tone: "neutral" },
};

const ContentReport = ({ check, issues }: { check: string | null; issues: DecisionPair[] }) => {
  const known = check === null ? null : (contentChecks[check] ?? { label: check, tone: "neutral" as Tone });
  return (
    <div className="flex flex-col gap-3">
      {known === null ? null : (
        <StatusBadge className="self-start" tone={known.tone}>
          {known.label}
        </StatusBadge>
      )}
      {issues.length === 0 ? (
        <p className="text-support text-cv-text-muted">לא נמצאו בעיות בתוכן.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {issues.map((issue) => (
            <li
              className="flex flex-col gap-1 rounded-control border border-cv-border bg-cv-surface-sunken px-3 py-2"
              key={`${issue.key}:${issue.value}`}
            >
              <span className="break-words text-support text-cv-text" dir="auto">
                {issue.value}
              </span>
              <LtrText className="break-all text-caption text-cv-text-muted" mono>
                {issue.key}
              </LtrText>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

const isPreparationState = (value: string): value is PreparationState => value in preparationStateLabels;

interface DecisionDocumentProps {
  decision: DecisionExport | undefined;
  onDownload: () => void;
  pending: boolean;
}

/* §16 `export_decision_markdown`: why the current document reads the way it does - the
   role it was built for, the classification that shaped it, the facts it draws on and
   its content check. It writes nothing, so this view offers reading and a download and
   nothing that edits it. Record ids and hashes stay in the downloaded file. */
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
  const classification = reading.classification.map(({ key, value }) => classified(key, value));
  const state =
    reading.preparationState === null
      ? null
      : isPreparationState(reading.preparationState)
        ? preparationStateLabels[reading.preparationState]
        : reading.preparationState;
  let step = 0;

  return (
    <article aria-labelledby="decision-document-title" className="flex flex-col gap-6 text-support text-cv-text">
      <header className="flex flex-col gap-3 rounded-surface border border-cv-border bg-cv-surface-sunken p-4 sm:p-5">
        <p className="text-caption font-semibold text-cv-text-muted">קורות החיים נבנו עבור</p>
        <h3
          className="break-words text-heading-card font-semibold text-cv-text"
          dir="auto"
          id="decision-document-title"
        >
          {reading.application ?? "המשרה הזו"}
        </h3>
        {state === null && reading.approvedAt === null ? null : (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            {state === null ? null : (
              <StatusBadge tone={reading.preparationState === "ready" ? "success" : "neutral"}>{state}</StatusBadge>
            )}
            {reading.approvedAt === null ? null : (
              <span className="text-caption text-cv-text-muted">
                אושר <DateTime value={reading.approvedAt} />
              </span>
            )}
          </div>
        )}
      </header>

      {classification.length === 0 && reading.overrides === null ? null : (
        <Part intro="הסיווג קבע את מבנה קורות החיים, את השפה ואת מה שמודגש בהם." step={++step} title="איך המשרה סווגה">
          <div className="flex flex-col gap-3">
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {classification.map((item) => (
                <div
                  className="flex min-w-0 flex-col gap-1 rounded-control border border-cv-border bg-cv-surface px-3 py-2.5"
                  key={item.term}
                >
                  <dt className="text-caption text-cv-text-muted">{item.term}</dt>
                  <dd className="break-words text-label font-semibold text-cv-text" dir="auto">
                    {item.value}
                  </dd>
                </div>
              ))}
            </dl>
            {reading.overrides === null ? null : reading.overrides === "" ? (
              <p className="text-caption text-cv-text-muted">הסיווג נשאר כפי שהניתוח קבע, בלי שינויים ידניים.</p>
            ) : (
              <p className="rounded-control border border-cv-border bg-cv-surface-sunken px-3 py-2 text-support">
                <span className="font-semibold">שינית ידנית: </span>
                <span dir="auto">{overridesText(reading.overrides)}</span>
              </p>
            )}
          </div>
        </Part>
      )}

      {reading.factIds === null ? null : (
        <Part
          count={reading.factIds.length}
          intro="כל טענה בקורות החיים נשענת על אחת מהעובדות האלה, ורק עליהן."
          step={++step}
          title="העובדות שקורות החיים נשענים עליהן"
        >
          <SelectedFacts ids={reading.factIds} language={reading.language} />
        </Part>
      )}

      {reading.contentCheck === null && reading.contentIssues.length === 0 ? null : (
        <Part intro="בדיקה שהתוכן תואם לעובדות ולכללי הניסוח." step={++step} title="בדיקת התוכן">
          <ContentReport check={reading.contentCheck} issues={reading.contentIssues} />
        </Part>
      )}

      <footer className="flex flex-col gap-2 border-t border-cv-border pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-caption text-cv-text-muted">הקובץ המלא, כפי שהשרת מפיק אותו מהמסמך הנוכחי.</p>
        <Button className="w-full sm:w-auto" onClick={onDownload} variant="secondary">
          <Download aria-hidden="true" className="size-icon-md" />
          הורדת מסמך ההחלטה
        </Button>
      </footer>
    </article>
  );
};
