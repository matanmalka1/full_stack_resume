import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Clock,
  FileCheck2,
  Plus,
  Search,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  type ApplicationListQuery,
  applicationListQueryOptions,
  closeApplication,
} from "../api/applications";
import type {
  ActivityFilter,
  ApplicationListItem,
  ApplicationPreset,
  ApplicationSort,
  PreparationState,
  RecruitmentStatus,
} from "../api/contracts";
import { isTerminalOperation } from "../api/operations";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { Button, buttonClasses } from "../ui/Button";
import { cx } from "../ui/cx";
import { Card } from "../ui/Card";
import { Dialog } from "../ui/Dialog";
import { PageHeading } from "../ui/PageHeading";
import { Select } from "../ui/Select";
import { StatusBadge } from "../ui/StatusBadge";
import type { StatusTone } from "../ui/status";
import { TextInput } from "../ui/TextInput";
import { actionDestination } from "./actionDestinations";
import {
  actionLabel,
  applicationPresetLabels,
  preparationStateIcons,
  preparationStateLabels,
  preparationStateTones,
  recruitmentStatusIcon,
  recruitmentStatusLabel,
  recruitmentStatusOrder,
  recruitmentStatusTone,
} from "./applicationLabels";
import { PAGE_SIZE, paramsFromQuery, queryFromParams } from "./applicationListParams";
import { operationTypeLabels, statusLabels } from "./operationLabels";
import { useDebouncedValue } from "./useDebouncedValue";

const dateFormat = new Intl.DateTimeFormat("he-IL", { dateStyle: "short" });

/* An unparsable timestamp is shown as it arrived rather than as "Invalid Date". */
const formatDate = (value: string): string => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : dateFormat.format(parsed);
};

/* Whether a tracked next action has passed its date.

   Derived here rather than carried by the projection, and deliberately so: the comparison
   is against the reader's own today, which only the browser knows. A server-computed flag
   would be stale from the moment it was cached - a board left open past midnight would go
   on reporting yesterday's answer until something refetched it.

   It invents no fact. `next_action_date` is the stored value, and this only reads it;
   nothing about which rows arrive changes, which stays the server's answer. Compared
   date-to-date rather than as timestamps, so an action due today is not overdue at 00:01,
   and an unparsable date is not overdue rather than being reported as an error. */
const isOverdue = (value: string | null | undefined, today: Date = new Date()): boolean => {
  if (value == null) {
    return false;
  }
  const due = new Date(value);
  if (Number.isNaN(due.getTime())) {
    return false;
  }
  const midnight = new Date(today);
  midnight.setHours(0, 0, 0, 0);
  return due < midnight;
};

/* How long the search field waits before it becomes a request. Long enough that a typed
   word is one question rather than seven, short enough that the board does not feel like
   it is lagging behind the field. */
const SEARCH_DEBOUNCE_MS = 300;

/* The initial that opens each row. Purely a pointer for the eye down a column of
   companies - it is `aria-hidden`, because a screen reader gets the company name itself
   from the cell beside it and the letter would only repeat its first character. */
const CompanyMark = ({ company }: { company: string }) => (
  <span
    aria-hidden="true"
    className="flex size-9 shrink-0 items-center justify-center rounded-control bg-cv-accent-soft text-support font-bold text-cv-accent"
  >
    {[...company][0] ?? "?"}
  </span>
);

/* The last column has no heading: it carries one icon control per row, and a word above
   it would be a label for a button that already states itself through `aria-label`. It is
   still a column rather than a control tucked into the one beside it, because that is what
   puts it in the same place on every row. */
const ARCHIVE_COLUMN = "";

const columns = [
  "חברה ותפקיד",
  "נוצר",
  "מצב קורות החיים",
  "שלב גיוס",
  "פעילות אחרונה",
  "הפעולה הבאה",
  "אזהרות",
  "פעולה מומלצת",
  ARCHIVE_COLUMN,
];

/* What each column is worth under `table-fixed`, keyed by the header it sits under.

   The two that carry sentences - the company with its role, and the recommended action
   with its archive control beside it - take the most. The dates and the warnings count are
   short, fixed-shape values and take the least; giving them an equal share was what left
   the headings floating over columns far wider than anything in them. */
const columnWidths: Record<string, string> = {
  "חברה ותפקיד": "w-[19%]",
  נוצר: "w-[8%]",
  "מצב קורות החיים": "w-[18%]",
  "שלב גיוס": "w-[11%]",
  "פעילות אחרונה": "w-[9%]",
  "הפעולה הבאה": "w-[11%]",
  אזהרות: "w-[7%]",
  "פעולה מומלצת": "w-[16%]",
  [ARCHIVE_COLUMN]: "w-[4%]",
};

/* The Hebrew for the two closed sets the backend defines. Keyed by the generated unions,
   so a filter or ordering added to the query fails the build here instead of reaching the
   control untranslated. */
const activityLabels: Record<ActivityFilter, string> = {
  open: "פעילות",
  closed: "סגורות",
  all: "הכול",
};

const sortLabels: Record<ApplicationSort, string> = {
  updated: "עודכן לאחרונה",
  created: "נוצר לאחרונה",
  company: "לפי חברה",
  stage: "לפי מצב קורות החיים",
};

/* Why the workflow is waiting, counted rather than spelled out.

   The projection carries every reason and warning in full, and the row has one line to
   say them in. A count beside the badge is what the row can honestly carry: it says there
   is something to read and how much of it, and the sentences themselves stay on the
   Application screen where the controls that resolve them are. Without it the badge said
   a decision was pending and gave no hint that two separate things were waiting. */
const attentionSummary = (item: ApplicationListItem): string | null => {
  const parts = [
    item.review_reasons.length === 0 ? null : `${item.review_reasons.length} להכרעה`,
    item.stale_reasons.length === 0 ? null : `${item.stale_reasons.length} לא מעודכן`,
    item.warnings.length === 0 ? null : `${item.warnings.length} אזהרות`,
  ].filter((part) => part !== null);

  return parts.length === 0 ? null : parts.join(" · ");
};

/* How loudly the attention cell speaks, by the most severe thing it is counting.

   A decision waiting on the user blocks the workflow, so it outranks a source that has
   merely drifted, which outranks a warning raised beside an Application that is otherwise
   fine. Colour is never the signal on its own - `StatusBadge` carries the icon and the
   counts are words - so this only picks which of them to use. */
const attentionTone = (item: ApplicationListItem): StatusTone => {
  if (item.review_reasons.length > 0) {
    return "blocker";
  }
  return item.stale_reasons.length > 0 || item.warnings.length > 0 ? "warning" : "neutral";
};

/* A closed Application is not offered closing again.

   `available_actions` does not answer this: that projection is the preparation workflow,
   and closing is the recruitment axis beside it. The row's own status is what says it,
   and `terminal_outcome` is the record's own answer wherever it is set. */
const closedStatuses = new Set(["rejected", "withdrawn", "closed"]);

const isClosed = (item: ApplicationListItem): boolean =>
  item.terminal_outcome != null || closedStatuses.has(item.recruitment_status);

/* The row's action, as a soft pill rather than a bordered button.

   One of these sits in every row, so the bordered secondary button that suits a page
   footer turned the column into a stack of boxes. The soft accent fill reads as one
   quiet control repeated down the board, and it still carries the action's name - the
   arrow only says which way it goes. Height comes down from the 44px page control: a
   table row is a denser context, and the pill is not the primary target on the screen. */
const rowActionClasses =
  "inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-pill bg-cv-accent-soft px-3.5 text-support font-semibold text-cv-accent transition-colors duration-200 hover:bg-cv-accent hover:text-cv-on-accent";

const ApplicationRow = ({
  ambiguous,
  item,
  onClose,
}: {
  ambiguous: boolean;
  item: ApplicationListItem;
  onClose: (item: ApplicationListItem) => void;
}) => {
  const href = `/applications/${encodeURIComponent(item.id)}`;
  /* What the workflow is waiting for, named by the projection rather than derived here.
     With nothing recommended the Application is not waiting on anything. */
  const next = item.recommended_action;
  const trackedNextAction = item.next_action;
  /* Live work, from the field the projection already carries. An Operation that has
     reached a terminal status is not work in progress any more, and the row says nothing
     about it: the stage badge beside it is the result. */
  const running =
    item.active_operation != null && !isTerminalOperation(item.active_operation)
      ? item.active_operation
      : null;
  const attention = attentionSummary(item);
  const overdue = isOverdue(item.next_action_date);
  const closed = isClosed(item);
  /* Only where the projection says a Ready record exists. The row is where a finished CV
     is collected from, and until now a Ready Application's next-action cell was an em
     dash - the one row that had produced something said the least about it. */
  const ready = item.latest_ready_revision_id;

  return (
    <tr className="border-b border-cv-border last:border-b-0 hover:bg-cv-surface-muted">
      <td className="px-4 py-3.5">
        <div className="flex min-w-0 items-center gap-2">
          <CompanyMark company={item.company} />
          <div className="min-w-0 flex-1 text-left">
            {/* One link per row, on the name: the row is a table row, and making every
                cell a link would be five tab stops to one destination. */}
            <Link
              className="block truncate text-support font-bold text-cv-text hover:underline"
              dir="auto"
              to={href}
            >
              {item.company}
            </Link>
            <p className="truncate text-support text-cv-text-muted" dir="auto">
              {item.target_role}
            </p>
          </div>
        </div>
      </td>
      {/* The creation date, on every row rather than only the ambiguous ones.

          It used to be a third line inside the company cell, shown just for the rows where
          two Applications share an opening - which meant the one column already carrying
          the most text grew taller on exactly the rows that were hardest to tell apart,
          and the date was absent everywhere the reader might have wanted to sort by it.
          As a column it is one short value per row, aligned down the board.

          `ambiguous` still marks its rows, but now by emphasis rather than by presence:
          the date is what distinguishes them, so on those rows it is the row's own text
          colour instead of the muted one every other row uses. */}
      <td className="whitespace-nowrap px-4 py-3.5 text-support">
        <span className={ambiguous ? "font-medium text-cv-text" : "text-cv-text-muted"}>
          {formatDate(item.created_at)}
        </span>
      </td>
      <td className="px-4 py-3.5">
        <StatusBadge
          className="whitespace-nowrap"
          icon={preparationStateIcons[item.preparation_state]}
          tone={preparationStateTones[item.preparation_state]}
        >
          {preparationStateLabels[item.preparation_state]}
        </StatusBadge>
      </td>
      <td className="px-4 py-3.5">
        <div className="flex flex-col items-start gap-1">
          {/* The recruitment axis carries a face per status, so a column of rows reads as
              distinct stages rather than as one long line of identical grey pills. An
              unknown status still gets a badge, in the neutral tone, rather than being
              dropped: the vocabulary is the backend's and this build may not know all
              of it. */}
          <StatusBadge
            className="whitespace-nowrap"
            icon={recruitmentStatusIcon(item.recruitment_status)}
            tone={recruitmentStatusTone(item.recruitment_status)}
          >
            {recruitmentStatusLabel(item.recruitment_status)}
          </StatusBadge>
          {/* A closed Application keeps its row and says so. Hidden by the default
              filter, it is still reachable, and when it is on screen it must not read
              like something still waiting on the user. */}
          {closed ? <span className="text-support text-cv-text-muted">התהליך נסגר</span> : null}
        </div>
      </td>
      <td className="whitespace-nowrap px-4 py-3.5 text-support text-cv-text-muted">
        <span className="inline-flex items-center gap-1.5">
          <Clock aria-hidden="true" className="size-3.5 shrink-0" />
          {formatDate(item.updated_at)}
        </span>
      </td>
      {/* The tracked next action, which is the user's own plan for this Application -
          distinct from the recommended action beside it, which is what the preparation
          workflow says to do. A row can carry both, and collapsing them into one cell
          meant a scheduled call hid the fact that a draft was waiting. */}
      <td className="px-4 py-3.5">
        {trackedNextAction == null ? (
          <span className="text-support text-cv-text-muted">טרם נקבעה</span>
        ) : (
          <div className="flex flex-col items-start gap-1">
            <span className="text-support text-cv-text" dir="auto">
              {trackedNextAction}
            </span>
            {item.next_action_date == null ? null : (
              <span className="flex items-center gap-1.5 text-support text-cv-text-muted">
                {/* Overdue is a comparison against the reader's own today, so it is said
                    here rather than carried by the projection. The word is what marks it;
                    the tone only repeats what the word already says. */}
                {overdue ? (
                  <StatusBadge className="gap-1 px-2 py-0.5" tone="warning">
                    באיחור
                  </StatusBadge>
                ) : null}
                <span className="inline-flex items-center gap-1.5">
                  <Clock aria-hidden="true" className="size-3.5 shrink-0" />
                  {formatDate(item.next_action_date)}
                </span>
              </span>
            )}
          </div>
        )}
      </td>

      {/* What is waiting on the user, counted. The sentences stay on the Application
          screen, where the controls that resolve them are; the row says that there is
          something to read and how much of it. */}
      <td className="px-4 py-3.5">
        {attention === null ? (
          /* An em dash: nothing is waiting on this row. It reads as quiet rather than as
             a state, which is what an empty warnings column should be - the eye should
             skip it and land on the rows that do carry a count. */
          <span className="text-support text-cv-text-muted">—</span>
        ) : (
          <StatusBadge tone={attentionTone(item)}>{attention}</StatusBadge>
        )}
      </td>

      {/* The recommended action, alone in its cell and starting at the column's edge like
          every other value on the board. The labels differ in length - "ניתוח המשרה"
          against "יצירת קובץ קורות החיים" - so anything but start-alignment gives the
          column a ragged left edge. */}
      <td className="whitespace-nowrap px-4 py-3.5">
        <div className="flex items-center">
          {running !== null ? (
            /* Work in progress outranks the recommended action: the action is what to do
               next, and while an Operation is running the answer is to wait for it. The
               spinning badge is the same vocabulary the Application screen uses. */
            <StatusBadge tone="progress">
              {operationTypeLabels[running.operation_type]} · {statusLabels[running.status]}
            </StatusBadge>
          ) : ready != null ? (
            /* The finished file, collected from the board. */
            <Link className={rowActionClasses} to={`/approved-revisions/${encodeURIComponent(ready)}/ready`}>
              <FileCheck2 aria-hidden="true" className="size-4" />
              הגרסה המוכנה
            </Link>
          ) : next == null ? (
            <span className="text-support text-cv-text-muted">—</span>
          ) : (
            /* Straight to the screen that takes the action, where one exists. The button
               names the action, so landing on the context screen instead asked the reader
               to find it a second time; `actionDestination` already answers which actions
               have a screen, and an action without one falls back to the Application. */
            <Link className={rowActionClasses} to={actionDestination(next, item.id) ?? href}>
              {/* The board is RTL, so the arrow into the row's destination points left. */}
              <ArrowLeft aria-hidden="true" className="size-4" />
              {actionLabel(next)}
            </Link>
          )}

        </div>
      </td>

      {/* Archiving, offered where the reader is deciding which Applications still matter.
          It is not a delete - the record and every approved revision stay exactly as they
          are - but it does move the Application off the live board, so it asks first. An
          already-closed row is not offered it again.

          Its own column, because sharing the action's cell made its position depend on how
          long that row's action label happened to be, and a control that moves between
          rows is one the reader has to find again on each of them. */}
      <td className="px-4 py-3.5">
        {closed ? null : (
          <Button
            aria-label={`סגירת המועמדות ${item.company}`}
            className="px-2"
            onClick={() => onClose(item)}
            variant="ghost"
          >
            <Archive aria-hidden="true" className="size-4" />
          </Button>
        )}
      </td>
    </tr>
  );
};

/* The controls that narrow the board.

   Each one edits the query the server answers. None of them filters or reorders what has
   already arrived: `preparation_state` is computed by the §9 projection rather than
   stored, so a client that narrowed by it would be deriving a second opinion about where
   an Application stands.

   The stage menu offers the states these Applications are actually in, counted by the
   server over all of them. Read off the page instead, the menu would collapse to the one
   stage the filter had already selected. */
/* The named questions, as one row of chips above the filters.

   Each chip sets the `preset` parameter and nothing else, so it narrows alongside the
   controls below rather than replacing them - a preset and a stage filter are one
   question with two clauses. The predicates are the application layer's: a chip names a
   question, it does not decide which rows answer it.

   Rendered as a radio group rather than as buttons, because that is what it is: the
   presets are mutually exclusive and "הכל" is the absence of one. Buttons would leave a
   keyboard reader tabbing through four controls to express one choice. */
const PresetChips = ({
  onChange,
  query,
}: {
  onChange: (query: ApplicationListQuery) => void;
  query: ApplicationListQuery;
}) => {
  const active = query.preset;
  const select = (preset: ApplicationPreset | undefined) =>
    onChange({ ...query, preset });

  /* The input is visually hidden but still the real control: it keeps the radio
     semantics, the arrow-key behaviour, and the label association a screen reader reads.

     The global `:focus-visible` ring would land on that hidden input, where nobody can
     see it, so the visible text beside it carries the ring instead. `peer` styles a later
     sibling, which is why the span follows the input rather than wrapping it. */
  const chip = (key: string, label: string, selected: boolean, onSelect: () => void) => (
    <label className="cursor-pointer" key={key}>
      <input
        checked={selected}
        className="peer sr-only"
        name="application-preset"
        onChange={onSelect}
        type="radio"
      />
      <span
        className={cx(
          "inline-flex items-center rounded-pill border px-3 py-1.5 text-support font-semibold transition-colors",
          "peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-cv-focus",
          selected
            ? "border-cv-accent bg-cv-accent-soft text-cv-accent"
            : "border-cv-border bg-cv-surface text-cv-text-muted hover:bg-cv-surface-muted",
        )}
      >
        {label}
      </span>
    </label>
  );

  return (
    <div aria-label="סינון מהיר" className="mt-6 flex flex-wrap items-center gap-2" role="radiogroup">
      {chip("all", "הכל", active === undefined, () => select(undefined))}
      {(Object.keys(applicationPresetLabels) as ApplicationPreset[]).map((preset) =>
        chip(preset, applicationPresetLabels[preset], active === preset, () => select(preset)),
      )}
    </div>
  );
};

/* The toolbar controls are filters, not form fields: shorter and fully rounded so the
   row reads as a strip of controls above the board rather than as a form to fill in. */
const toolbarControlClasses = "mt-1 min-h-9 rounded-xl py-1.5";

const ListToolbar = ({
  onChange,
  onSearch,
  query,
  search,
  stageCounts,
}: {
  onChange: (query: ApplicationListQuery) => void;
  onSearch: (search: string) => void;
  query: ApplicationListQuery;
  search: string;
  stageCounts: Partial<Record<PreparationState, number>>;
}) => (
  <div className="mt-3 flex flex-wrap items-end gap-3">
    <div className="min-w-[14rem] flex-1">
      <label className="block text-support font-semibold text-cv-text" htmlFor="list-search">
        חיפוש
      </label>
      <div className="relative mt-1">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 start-3 my-auto size-4 text-cv-text-muted"
        />
        {/* The field is uncontrolled by the query on purpose: it holds what is being
            typed, and only the settled value becomes a request. */}
        <TextInput
          className={cx(toolbarControlClasses, "ps-8")}
          dir="rtl"
          id="list-search"
          onChange={(event) => onSearch(event.target.value)}
          placeholder="חברה או תפקיד"
          type="search"
          value={search}
        />
      </div>
    </div>

    <div>
      <label className="block text-support font-semibold text-cv-text" htmlFor="list-activity">
        מועמדויות
      </label>
      <Select
        className={toolbarControlClasses}
        id="list-activity"
        onChange={(event) => onChange({ ...query, activity: event.target.value as ActivityFilter })}
        value={query.activity ?? "open"}
      >
        {(Object.keys(activityLabels) as ActivityFilter[]).map((key) => (
          <option key={key} value={key}>
            {activityLabels[key]}
          </option>
        ))}
      </Select>
    </div>

    <div>
      <label className="block text-support font-semibold text-cv-text" htmlFor="list-stage">
        מצב קורות החיים
      </label>
      <Select
        className={toolbarControlClasses}
        id="list-stage"
        onChange={(event) =>
          onChange({
            ...query,
            /* A list because the endpoint repeats `stage`. The control offers one at a
               time; a multi-select can be added over the same parameter without changing
               what is sent. */
            stages: event.target.value === "" ? [] : [event.target.value as PreparationState],
          })
        }
        value={query.stages?.[0] ?? ""}
      >
        <option value="">הכול</option>
        {/* Ordered by the label map, which is the workflow order, rather than by
            whatever order the counts arrived in. */}
        {(Object.keys(preparationStateLabels) as PreparationState[])
          .filter((stage) => (stageCounts[stage] ?? 0) > 0)
          .map((stage) => (
            <option key={stage} value={stage}>
              {preparationStateLabels[stage]} ({stageCounts[stage]})
            </option>
          ))}
      </Select>
    </div>

    {/* The recruitment axis, beside the CV-state filter rather than merged into it. The
        two are independent - where the CV has got to, and where the Application stands
        with the employer - so one control could not express a question about both. */}
    <div>
      <label
        className="block text-support font-semibold text-cv-text"
        htmlFor="list-recruitment-status"
      >
        שלב גיוס
      </label>
      <Select
        className={toolbarControlClasses}
        id="list-recruitment-status"
        onChange={(event) =>
          onChange({
            ...query,
            /* A list because the endpoint repeats `recruitment_status`. The control
               offers one at a time; a multi-select can be added over the same parameter
               without changing what is sent. */
            recruitmentStatuses:
              event.target.value === "" ? [] : [event.target.value as RecruitmentStatus],
          })
        }
        value={query.recruitmentStatuses?.[0] ?? ""}
      >
        <option value="">כל שלבי הגיוס</option>
        {recruitmentStatusOrder.map((status) => (
          <option key={status} value={status}>
            {recruitmentStatusLabel(status)}
          </option>
        ))}
      </Select>
    </div>

    <div>
      <label className="block text-support font-semibold text-cv-text" htmlFor="list-sort">
        סדר
      </label>
      <Select
        className={toolbarControlClasses}
        id="list-sort"
        onChange={(event) => onChange({ ...query, sort: event.target.value as ApplicationSort })}
        value={query.sort ?? "updated"}
      >
        {(Object.keys(sortLabels) as ApplicationSort[]).map((key) => (
          <option key={key} value={key}>
            {sortLabels[key]}
          </option>
        ))}
      </Select>
    </div>
  </div>
);

/* Which rows on this page a reader cannot tell apart: same company, same role.

   Over the page rather than the whole list, which is also the right scope: a pair split
   across two pages is not a collision the reader can see, and dating one row of it would
   explain nothing. */
const duplicatedIdentities = (items: readonly ApplicationListItem[]): ReadonlySet<string> => {
  const byIdentity = new Map<string, string[]>();

  for (const item of items) {
    const key = `${item.company}\n${item.target_role}`;
    byIdentity.set(key, [...(byIdentity.get(key) ?? []), item.id]);
  }

  return new Set([...byIdentity.values()].filter((ids) => ids.length > 1).flat());
};

/* The screen behind `/`: every Application this instance holds, as a board.

   It is the root because an existing Application has to be reachable without its URL.
   With the intake form here instead, the wordmark - the one gesture every user reads as
   "home" - started a new Application, and a saved one could only be reached by going back
   through history.

   A table rather than a stack of cards: the columns are what make two Applications
   comparable at a glance, which is the question this screen answers - where does each one
   stand, and which is waiting on me.

   Narrowing, ordering, and paging are the server's answers, and the question lives in the
   address bar. This screen holds neither a filtered copy of the rows nor a private copy of
   the query; it renders the page that comes back. */
export const ApplicationListPage = () => {
  const [params, setParams] = useSearchParams();
  const query = queryFromParams(params);
  const queryClient = useQueryClient();

  /* What is being typed, which is not yet what is being asked. The settled value goes
     into the URL, so the address bar carries questions the user finished asking rather
     than every prefix of them. */
  const [typed, setTyped] = useState(query.search ?? "");
  const settled = useDebouncedValue(typed, SEARCH_DEBOUNCE_MS);
  const [closing, setClosing] = useState<ApplicationListItem | null>(null);

  const listQuery = useQuery(applicationListQueryOptions(query));
  const page = listQuery.data;

  /* Outside the per-Application workflow: this screen stands before any of them, so no
     stage is the honest answer and the landmark reports nothing. */
  useWorkflowStage("none");

  /* Any control other than the pager returns to the first page. The offset names a
     position in an ordering, so keeping it across a change to that ordering would land
     the reader in the middle of an answer to a question they just changed.

     `replace` so that narrowing does not fill the history with every intermediate board;
     the pager below pushes, because moving between pages is a step worth going back over. */
  const narrow = (next: ApplicationListQuery) =>
    setParams(paramsFromQuery({ ...next, offset: 0 }), { replace: true });

  /* The settled search reaches the URL from here rather than from the field's handler:
     it is the one control whose value arrives later than the gesture that set it. */
  useEffect(() => {
    if (settled !== (query.search ?? "")) {
      narrow({ ...query, search: settled });
    }
    /* Deliberately keyed on the settled value alone. Re-running when `query` changes
       would fight the URL: every other control rewrites the query, and this effect would
       then rewrite it back with a search that had not changed. */
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settled]);

  /* Archiving is a status transition, so the answer is not cached anywhere this screen
     can patch: the list is re-read, and the Application screen with it, in case the row
     that was closed is also open in another tab. */
  const close = useMutation({
    mutationFn: (applicationId: string) => closeApplication(applicationId),
    onSuccess: async () => {
      setClosing(null);
      await queryClient.invalidateQueries({ queryKey: ["applications"] });
      await queryClient.invalidateQueries({ queryKey: ["application"] });
    },
  });

  const offset = query.offset ?? 0;
  const items = page?.items ?? [];
  const ambiguous = duplicatedIdentities(items);
  const matched = page?.matched ?? 0;
  const hasMore = offset + items.length < matched;

  const newApplication = (
    <Link className={buttonClasses("primary")} to="/applications/new">
      <Plus aria-hidden="true" className="size-4" />
      משרה חדשה
    </Link>
  );

  return (
    <Card aria-labelledby="route-heading">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b border-cv-border pb-4">
        <PageHeading description="מעקב אחר תהליכי התאמת קורות החיים למשרות." id="route-heading">
          המועמדויות
        </PageHeading>
        {newApplication}
      </div>

      {listQuery.error === null ? null : (
        <ErrorCallout
          className="mt-6"
          error={listQuery.error}
          fallbackDetail="הפנייה לשרת נכשלה. אפשר לרענן את העמוד ולנסות שוב."
          fallbackTitle="לא ניתן לטעון את המועמדויות"
        />
      )}

      {close.error === null ? null : (
        <ErrorCallout
          className="mt-6"
          error={close.error}
          fallbackDetail="המועמדות לא נסגרה. אפשר לנסות שוב."
          fallbackTitle="סגירת המועמדות נכשלה"
        />
      )}

      {page === undefined ? (
        listQuery.error === null ? (
          <p className="mt-6 text-body text-cv-text-muted">טוען את המועמדויות…</p>
        ) : null
      ) : page.total === 0 ? (
        /* The database starts empty, so this is the first thing a new installation shows.
           It says what the screen is for and offers the one action that fills it. The
           condition is `total`, the count before the query narrowed anything: a filter
           that matched nothing is a different situation and gets a different answer. */
        <div className="mt-6 rounded-surface border border-dashed border-cv-border p-8 text-center">
          <p className="text-body text-cv-text">עוד לא נוצרה אף מועמדות.</p>
          <p className="mt-1 text-support text-cv-text-muted">
            מועמדות חדשה מתחילה בהדבקת מודעת המשרה.
          </p>
          <div className="mt-5 flex justify-center">{newApplication}</div>
        </div>
      ) : (
        <>
          <PresetChips onChange={narrow} query={query} />

          <ListToolbar
            onChange={narrow}
            onSearch={setTyped}
            query={query}
            search={typed}
            stageCounts={page.stage_counts}
          />

          {/* What the query answered, said out loud. The table is long enough to scroll
              past the toolbar, so a narrowed board and a whole one have to be
              distinguishable without counting rows. */}
          <p aria-live="polite" className="mt-3 text-support text-cv-text-muted">
            {matched === page.total
              ? `${page.total} מועמדויות`
              : `${matched} מתוך ${page.total} מועמדויות`}
          </p>

          {items.length === 0 ? (
            /* Distinct from the empty database above: there are Applications, and the
               query is what is hiding them. Saying so with the way back is the difference
               between a narrowed board and a broken one. */
            <div className="mt-4 rounded-surface border border-dashed border-cv-border p-8 text-center">
              <p className="text-body text-cv-text">אין מועמדות שמתאימה לסינון.</p>
              <div className="mt-5 flex justify-center">
                <Button
                  onClick={() => {
                    setTyped("");
                    setParams(new URLSearchParams(), { replace: true });
                  }}
                  variant="secondary"
                >
                  ניקוי הסינון
                </Button>
              </div>
            </div>
          ) : (
            /* The table scrolls inside its own container rather than widening the page:
               nine columns of Hebrew, dates, and status pills do not fit a narrow
               viewport, and a horizontally scrolling body would take the header with it.

               The floor is the width below which the columns genuinely stop working, not
               the width they would like: set above it, the board scrolled sideways on
               displays that had room for it and truncated the role text while doing so.

               The container is pulled out to the Card's edge. Nested inside the padding it
               was a bordered surface inset within a bordered surface - two rules and two
               gutters around one table - and the inset came straight off the width the
               columns had to share, which is what made them wrap on a display with room
               to spare. The negative margin is matched to the Card's own padding at each
               breakpoint, so the board meets the card edge rather than overhanging it. */
            <div className="-mx-5 mt-4 overflow-x-auto border-y border-cv-border bg-cv-surface-raised sm:-mx-8">
              {/* `table-fixed` so the columns are laid out by the header row rather than
                  by whichever row happens to hold the longest company name. With automatic
                  layout every cell's content bid for width, so a header sat at the start
                  of a column whose width had been decided by a value three rows down - the
                  heading and the values under it visibly disagreed about where the column
                  began. Fixed layout gives each column the share below and keeps the
                  header over its own values. */}
              <table className="w-full min-w-[64rem] table-fixed border-collapse text-start">
                <thead>
                  {/* A tinted band rather than a bare rule. The board is a long list of
                      similar rows, and a header that shares their background stops
                      reading as a header once the page is scrolled to it. */}
                  <tr className="border-b border-cv-border bg-cv-surface-muted">
                    {columns.map((column) => (
                      <th
                        className={cx(
                          "px-4 py-3 text-start text-support font-semibold text-cv-text-muted",
                          columnWidths[column],
                        )}
                        key={column}
                        scope="col"
                      >
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <ApplicationRow
                      ambiguous={ambiguous.has(item.id)}
                      item={item}
                      key={item.id}
                      onClose={setClosing}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Only once there is a second page. A pager under a board that fits on one
              screen is a control that can never do anything. */}
          {offset > 0 || hasMore ? (
            <nav
              aria-label="ניווט בין דפי המועמדויות"
              className="mt-4 flex flex-wrap items-center justify-between gap-3"
            >
              <p className="text-support text-cv-text-muted">
                {`${offset + 1}–${offset + items.length} מתוך ${matched}`}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  disabled={offset === 0}
                  onClick={() =>
                    setParams(
                      paramsFromQuery({ ...query, offset: Math.max(0, offset - PAGE_SIZE) }),
                    )
                  }
                  variant="secondary"
                >
                  {/* The board is RTL, so "previous" points to the right. */}
                  <ChevronRight aria-hidden="true" className="size-4" />
                  הקודם
                </Button>
                <Button
                  disabled={!hasMore}
                  onClick={() =>
                    setParams(paramsFromQuery({ ...query, offset: offset + PAGE_SIZE }))
                  }
                  variant="secondary"
                >
                  הבא
                  <ChevronLeft aria-hidden="true" className="size-4" />
                </Button>
              </div>
            </nav>
          ) : null}
        </>
      )}

      {/* Closing keeps everything and hides nothing permanently, but it does move an
          Application off the board the user works from, so it is confirmed rather than
          taken on one click of a small icon. */}
      <Dialog
        footer={
          <>
            <Button onClick={() => setClosing(null)} variant="secondary">
              ביטול
            </Button>
            <Button
              disabled={close.isPending}
              onClick={() => {
                if (closing !== null) {
                  close.mutate(closing.id);
                }
              }}
            >
              {close.isPending ? "סוגר…" : "סגירת המועמדות"}
            </Button>
          </>
        }
        headingId="close-application-heading"
        onClose={() => setClosing(null)}
        open={closing !== null}
        title="לסגור את המועמדות?"
      >
        <p dir="auto">
          {closing === null
            ? null
            : `${closing.company} — ${closing.target_role} תסומן כסגורה ותרד מלוח המועמדויות הפעילות.`}
        </p>
        <p className="mt-2 text-support text-cv-text-muted">
          שום דבר לא נמחק. תצלום המשרה, הטיוטות והגרסאות שאושרו נשמרים כפי שהם, והמועמדות
          נשארת נגישה דרך הסינון.
        </p>
      </Dialog>
    </Card>
  );
};
