import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { applicationListQueryOptions } from "../api/applications";
import type { ApplicationListItem } from "../api/contracts";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { buttonClasses } from "../ui/Button";
import { Card } from "../ui/Card";
import { PageHeading } from "../ui/PageHeading";
import { StatusBadge } from "../ui/StatusBadge";
import { actionDestination } from "./actionDestinations";
import {
  actionLabel,
  preparationStateLabels,
  preparationStateTones,
  recruitmentStatusLabel,
} from "./applicationLabels";

const dateFormat = new Intl.DateTimeFormat("he-IL", { dateStyle: "short" });

/* An unparsable timestamp is shown as it arrived rather than as "Invalid Date". */
const formatDate = (value: string): string => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : dateFormat.format(parsed);
};

/* The initial that opens each row. Purely a pointer for the eye down a column of
   companies - it is `aria-hidden`, because a screen reader gets the company name itself
   from the cell beside it and the letter would only repeat its first character. */
const CompanyMark = ({ company }: { company: string }) => (
  <span
    aria-hidden="true"
    className="flex size-8 shrink-0 items-center justify-center rounded-pill bg-cv-surface-muted text-support font-bold text-cv-text-muted"
  >
    {[...company][0] ?? "?"}
  </span>
);

const columns = ["חברה ותפקיד", "מצב קורות החיים", "שלב גיוס", "עודכן", "הפעולה הבאה"];

const ApplicationRow = ({ item }: { item: ApplicationListItem }) => {
  const href = `/applications/${encodeURIComponent(item.id)}`;
  /* What the workflow is waiting for, named by the projection rather than derived here.
     With nothing recommended the Application is not waiting on anything. */
  const next = item.recommended_action;

  return (
    <tr className="border-b border-cv-border last:border-b-0 hover:bg-cv-surface-muted">
      <td className="p-3">
        <div className="flex min-w-0 items-center gap-3">
          <CompanyMark company={item.company} />
          <div className="min-w-0">
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
      <td className="p-3">
        <StatusBadge tone={preparationStateTones[item.preparation_state]}>
          {preparationStateLabels[item.preparation_state]}
        </StatusBadge>
      </td>
      <td className="p-3">
        <span className="whitespace-nowrap rounded-pill border border-cv-border bg-cv-surface-muted px-3 py-1 text-support text-cv-text-muted">
          {recruitmentStatusLabel(item.recruitment_status)}
        </span>
      </td>
      <td className="whitespace-nowrap p-3 text-support text-cv-text-muted">
        {formatDate(item.updated_at)}
      </td>
      <td className="p-3">
        {next == null ? (
          <span className="text-support text-cv-text-muted">—</span>
        ) : (
          /* Straight to the screen that takes the action, where one exists. The button
             names the action, so landing on the context screen instead asked the reader
             to find it a second time; `actionDestination` already answers which actions
             have a screen, and an action without one falls back to the Application. */
          <Link className={buttonClasses("secondary")} to={actionDestination(next, item.id) ?? href}>
            {actionLabel(next)}
          </Link>
        )}
      </td>
    </tr>
  );
};

/* The screen behind `/`: every Application this instance holds, as a board.

   It is the root because an existing Application has to be reachable without its URL.
   With the intake form here instead, the wordmark - the one gesture every user reads as
   "home" - started a new Application, and a saved one could only be reached by going back
   through history.

   A table rather than a stack of cards: the columns are what make two Applications
   comparable at a glance, which is the question this screen answers - where does each one
   stand, and which is waiting on me. */
export const ApplicationListPage = () => {
  const query = useQuery(applicationListQueryOptions);
  const items = query.data;

  /* Outside the per-Application workflow: this screen stands before any of them, so no
     stage is the honest answer and the landmark reports nothing. */
  useWorkflowStage("none");

  const newApplication = (
    <Link className={buttonClasses("primary")} to="/applications/new">
      <Plus aria-hidden="true" className="size-4" />
      משרה חדשה
    </Link>
  );

  return (
    <Card aria-labelledby="route-heading">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b border-cv-border pb-4">
        <PageHeading
          description="מעקב אחר תהליכי התאמת קורות החיים למשרות."
          id="route-heading"
        >
          המועמדויות
        </PageHeading>
        {newApplication}
      </div>

      {query.error === null ? null : (
        <ErrorCallout
          className="mt-6"
          error={query.error}
          fallbackDetail="הפנייה לשרת נכשלה. אפשר לרענן את העמוד ולנסות שוב."
          fallbackTitle="לא ניתן לטעון את המועמדויות"
        />
      )}

      {items === undefined ? (
        query.error === null ? (
          <p className="mt-6 text-body text-cv-text-muted">טוען את המועמדויות…</p>
        ) : null
      ) : items.length === 0 ? (
        /* The database starts empty, so this is the first thing a new installation shows.
           It says what the screen is for and offers the one action that fills it. */
        <div className="mt-6 rounded-surface border border-dashed border-cv-border p-8 text-center">
          <p className="text-body text-cv-text">עוד לא נוצרה אף מועמדות.</p>
          <p className="mt-1 text-support text-cv-text-muted">
            מועמדות חדשה מתחילה בהדבקת מודעת המשרה.
          </p>
          <div className="mt-5 flex justify-center">{newApplication}</div>
        </div>
      ) : (
        /* The table scrolls inside its own container rather than widening the page: five
           columns of Hebrew and dates do not fit a narrow viewport, and a horizontally
           scrolling body would take the header with it. */
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[48rem] border-collapse text-start">
            <thead>
              <tr className="border-b border-cv-border">
                {columns.map((column) => (
                  <th
                    className="p-3 text-start text-support font-semibold text-cv-text-muted"
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
                <ApplicationRow item={item} key={item.id} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
};
