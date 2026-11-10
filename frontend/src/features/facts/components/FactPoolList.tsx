import { AlertTriangle, CircleCheck } from "lucide-react";
import { createElement } from "react";
import { Link } from "react-router-dom";

import type { Fact } from "@/api/contracts";
import { cx } from "@/ui/cx";
import {
  factContextLine,
  factKindSections,
  factLabel,
  factSourceIcon,
  factSourceLabel,
  factStatusLabels,
  factStyleLabel,
} from "../model/factLabels";
import { type FactPoolEntry, type FactSourceGroup, groupFactPool } from "../model/factPool";
import { FactStatusBadge } from "./FactStatusBadge";

/* Kinds whose facts are a few words each - a phone number, a title, a date range. A wide
   screen sets them two to a row so a file's contact block does not run the page's height. */
const COMPACT_KINDS = new Set(["contact", "heading", "date"]);

/* A tag that repeats the file's own name says nothing the section heading has not. */
const SOURCE_TAGS: Record<string, string[]> = {
  "common.json": [],
  "development.json": ["development"],
  "sales.json": ["sales"],
  "situational_skills.json": ["situational"],
};

const HEBREW = /[\u0590-\u05FF]/u;

const anchorPart = (value: string): string => value.replaceAll(/[^a-z0-9]+/giu, "-").toLowerCase();
const sourceAnchor = (source: string): string => `fact-file-${anchorPart(source)}`;
const kindAnchor = (source: string, style: string): string => `${sourceAnchor(source)}-${anchorPart(style)}`;

const OutOfSyncMark = () => (
  <span
    aria-label="מצב העובדה אינו תואם למצב האחרון ביומן"
    className="relative inline-flex shrink-0 items-center text-cv-blocker"
    // The icon inside is aria-hidden; role="img" presents it as one image for assistive
    // tech, which `<img>` (a void element) cannot do.
    // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
    role="img"
  >
    <AlertTriangle aria-hidden="true" className="size-icon-md" />
  </span>
);

/* A settled fact is the pool's normal state, so it draws as a quiet mark with its word as
   the accessible name; only a state the reader has to notice - waiting, or deleted -
   draws as a pill. */
const StatusMark = ({ fact }: { fact: Fact }) =>
  fact.status === "canonical" ? (
    <span
      aria-label={factStatusLabels.canonical}
      className="inline-flex text-cv-text-muted/70"
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      role="img"
    >
      <CircleCheck aria-hidden="true" className="size-4.5" />
    </span>
  ) : (
    <FactStatusBadge status={fact.status} />
  );

/* Tags that every fact of a kind shares ("contact" under each contact detail) or that
   name the file itself repeat a heading the reader already sees. */
const redundantTags = (source: string, entries: FactPoolEntry[]): Set<string> => {
  const [first, ...rest] = entries;
  const shared = (first?.fact.tags ?? []).filter((tag) => rest.every(({ fact }) => fact.tags.includes(tag)));
  return new Set([...(SOURCE_TAGS[source] ?? []), ...(entries.length > 1 ? shared : [])]);
};

const FactRow = ({
  entry,
  factHref,
  hiddenTags,
}: {
  entry: FactPoolEntry;
  factHref: (factId: string) => string;
  hiddenTags: Set<string>;
}) => {
  const { fact, outOfSync } = entry;
  const context = factContextLine(fact);
  const tags = fact.tags.filter((tag) => !hiddenTags.has(tag)).slice(0, 3);
  const label = factLabel(fact);
  /* Hebrew wording reads right to left even when it opens with an English name; wording
     with no Hebrew at all (a phone number, a URL) reads left to right but keeps to the
     list's right edge, where every other row starts. */
  const hebrew = HEBREW.test(label);

  return (
    <li
      className={cx(
        "relative flex items-start gap-3 border-t border-cv-hairline px-4 py-3.5 transition-colors hover:bg-cv-canvas/70 lg:px-5",
        fact.status === "pending" && "bg-cv-canvas/50",
      )}
    >
      <div className="min-w-0 flex-1">
        {/* The link's box stretches over the whole row: the row is one target. */}
        <Link
          className={cx(
            "line-clamp-3 text-body leading-snug font-medium text-cv-text after:absolute after:inset-0 after:content-['']",
            !hebrew && "text-end",
          )}
          dir={hebrew ? "rtl" : "ltr"}
          to={factHref(fact.fact_id)}
        >
          {label}
        </Link>
        {/* A phone keeps the row to its wording and dates; the tags need a wide screen. */}
        {context === "" && tags.length === 0 ? null : (
          <p
            className={cx(
              "mt-1.5 flex-wrap items-center gap-x-2 gap-y-1 text-caption text-cv-text-muted",
              context === "" ? "hidden md:flex" : "flex",
            )}
          >
            {context === "" ? null : (
              <span className="font-medium tabular-nums" dir="ltr">
                {context}
              </span>
            )}
            {tags.map((tag) => (
              <span className="rounded-pill bg-cv-canvas px-2 py-px max-md:hidden" dir="ltr" key={tag}>
                {tag}
              </span>
            ))}
          </p>
        )}
      </div>
      <span className="flex shrink-0 items-center gap-2 pt-0.5">
        {outOfSync ? <OutOfSyncMark /> : null}
        <StatusMark fact={fact} />
      </span>
    </li>
  );
};

const SourceSection = ({ factHref, group }: { factHref: (factId: string) => string; group: FactSourceGroup }) => {
  const headingId = `${sourceAnchor(group.source)}-heading`;
  const pending = group.entries.filter(({ fact }) => fact.status === "pending").length;

  return (
    <section
      aria-labelledby={headingId}
      className="scroll-mt-6 overflow-hidden rounded-surface border border-cv-hairline bg-cv-surface shadow-surface"
      id={sourceAnchor(group.source)}
    >
      <header className="flex items-center gap-3.5 px-4 py-4 lg:px-5">
        <span
          aria-hidden="true"
          className="flex size-10 shrink-0 items-center justify-center rounded-control bg-cv-accent text-cv-on-accent"
        >
          {createElement(factSourceIcon(group.source), { className: "size-5" })}
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-heading-card font-bold text-cv-text" dir="auto" id={headingId}>
            {factSourceLabel(group.source)}
          </h2>
          <p className="text-caption text-cv-text-muted">
            <span className="tabular-nums">{group.entries.length}</span> עובדות
            {pending === 0 ? null : (
              <>
                {" · "}
                <span className="font-bold text-cv-text tabular-nums">{pending}</span> ממתינות לאישור
              </>
            )}
          </p>
        </div>
      </header>

      {group.kinds.map((kind) => {
        const hiddenTags = redundantTags(group.source, kind.entries);
        return (
          <div className="scroll-mt-6" id={kindAnchor(group.source, kind.style)} key={kind.style}>
            <h3 className="flex items-baseline justify-between gap-3 border-t border-cv-hairline bg-cv-canvas/70 px-4 py-2 text-caption font-bold text-cv-text-muted lg:px-5">
              <span>{kind.label}</span> <span className="font-medium tabular-nums">{kind.entries.length}</span>
            </h3>
            <ul
              className={cx(
                COMPACT_KINDS.has(kind.style) &&
                  kind.entries.length > 1 &&
                  "md:grid md:grid-cols-2 md:[&>li:last-child:nth-child(odd)]:col-span-2 md:[&>li:nth-child(odd):not(:last-child)]:border-e",
              )}
            >
              {kind.entries.map((entry) => (
                <FactRow entry={entry} factHref={factHref} hiddenTags={hiddenTags} key={entry.fact.fact_id} />
              ))}
            </ul>
          </div>
        );
      })}
    </section>
  );
};

/* A wide screen keeps the pool's outline beside it: every file and the kinds inside it,
   each a jump to its section. A phone narrows by the chips above instead. */
const PoolContents = ({ groups }: { groups: FactSourceGroup[] }) => (
  <nav aria-label="תוכן המאגר" className="sticky top-6 max-lg:hidden">
    <p className="mb-2 px-2.5 text-caption font-bold text-cv-text-muted">תוכן המאגר</p>
    <ol className="flex flex-col gap-1">
      {groups.map((group) => (
        <li key={group.source}>
          <a
            className="flex items-center gap-2.5 rounded-control-sm px-2.5 py-2 text-label font-bold text-cv-text transition-colors hover:bg-cv-surface"
            href={`#${sourceAnchor(group.source)}`}
          >
            {createElement(factSourceIcon(group.source), {
              "aria-hidden": true,
              className: "size-icon-md shrink-0 text-cv-text-muted",
            })}
            <span className="min-w-0 flex-1 truncate" dir="auto">
              {factSourceLabel(group.source)}
            </span>{" "}
            <span className="font-medium text-cv-text-muted tabular-nums">{group.entries.length}</span>
          </a>
          <ol className="mb-1 flex flex-col">
            {group.kinds.map((kind) => (
              <li key={kind.style}>
                <a
                  className="flex items-center gap-2 rounded-control-sm py-1 ps-9 pe-2.5 text-support text-cv-text-muted transition-colors hover:bg-cv-surface hover:text-cv-text"
                  href={`#${kindAnchor(group.source, kind.style)}`}
                >
                  <span className="min-w-0 flex-1 truncate">{kind.label}</span>{" "}
                  <span className="tabular-nums">{kind.entries.length}</span>
                </a>
              </li>
            ))}
          </ol>
        </li>
      ))}
    </ol>
  </nav>
);

/* The pool, ordered twice: a section per knowledge file, and inside it a block per kind of
   fact in the order a CV reads them. Every fact is one row and the whole row is its link. */
export const FactPoolList = ({
  entries,
  factHref,
}: {
  entries: FactPoolEntry[];
  factHref: (factId: string) => string;
}) => {
  const groups = groupFactPool(entries, factKindSections, factStyleLabel);

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_14rem] xl:gap-8">
      <section aria-label="רשימת העובדות" className="flex min-w-0 flex-col gap-4 lg:gap-5">
        {groups.map((group) => (
          <SourceSection factHref={factHref} group={group} key={group.source} />
        ))}
      </section>
      <PoolContents groups={groups} />
    </div>
  );
};
