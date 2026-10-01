import { routePaths } from "./routePaths";

/* Where "back to the board" goes, with the board still filtered the way the reader left
   it.

   The board keeps its whole state in the query string, so returning to the bare path is
   returning to a different board: filter to "needs attention", open an Application, press
   the breadcrumb, and every filter is gone. The intake screen already solved this for
   itself by carrying the board's search through its own link, which is why that one round
   trip worked and the three record screens did not.

   Carried here rather than in each link because the record screens sit at varying depths -
   board, Application, editor, Ready - and threading a search parameter through every
   hop would put the board's filters in the URL of records that have nothing to do with
   them, where a shared link would hand someone else a filtered board they never chose.

   `sessionStorage` rather than a module variable so the answer survives a reload of a
   record screen, and per tab so two tabs on two different filterings do not overwrite each
   other. Every access is guarded: a private window, blocked site data, or a prerender can
   throw on the accessor itself, and a board that cannot be remembered is simply a board
   returned to unfiltered. */
const STORAGE_KEY = "cv:board-query";

export const rememberBoardQuery = (search: string): void => {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, search);
  } catch {
    /* Remembering is a convenience; failing to is not worth an error to the reader. */
  }
};

/* The board's path, with the last remembered query where there is one. The fallback is
   the bare board, which is the honest answer when nothing was remembered - never a
   half-applied filtering. */
export const boardPath = (): string => {
  let search = "";
  try {
    search = window.sessionStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return routePaths.home;
  }

  return search === "" ? routePaths.home : `${routePaths.home}?${search}`;
};

/* Which Application the reader is coming back to the board from, carried in the history
   entry of the link that leaves a flow screen. The board uses it once - to find that card
   for the reader and mark it for a moment - and never as a filter or an order: the board
   stays exactly as it was left. History state rather than the query string, so a shared
   or reloaded board URL carries no trace of it. */
interface BoardReturnState {
  returnedFrom: string;
}

export const boardReturnState = (applicationId: string | undefined): BoardReturnState | undefined =>
  applicationId === undefined ? undefined : { returnedFrom: applicationId };

export const returnedApplicationId = (state: unknown): string | null =>
  typeof state === "object" &&
  state !== null &&
  "returnedFrom" in state &&
  typeof (state as BoardReturnState).returnedFrom === "string"
    ? (state as BoardReturnState).returnedFrom
    : null;
