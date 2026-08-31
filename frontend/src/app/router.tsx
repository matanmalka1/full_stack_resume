import { Navigate, createBrowserRouter, useParams } from "react-router-dom";

import { App } from "../App";
import { ApplicationListPage } from "../pages/ApplicationListPage";
import { ApplicationPage } from "../pages/ApplicationPage";
import { DraftEditorPage } from "../pages/draft-editor/DraftEditorPage";
import { NewApplicationPage } from "../pages/NewApplicationPage";
import { RevisionPage } from "../pages/RevisionPage";
import { RoutePlaceholder } from "../pages/RoutePlaceholder";
import { SettingsPage } from "../pages/SettingsPage";
import { RouteErrorBoundary } from "./RouteErrorBoundary";

/* The root is the Application list, and intake is a screen reached from it. The two were
   the other way round until the list existed at all: with the form at `/`, the wordmark
   started a new Application instead of going home, and a saved one was reachable only by
   its URL or the back button.

   Recruitment tracking is not a screen. It is the Application's other axis, and it is a
   view of the Application screen rather than a route: the two shared the masthead, the
   projection read, the error handling, and the switch itself, and differed only in which
   panel sat beneath. `?view=tracking` keeps it reloadable and bookmarkable without
   keeping a second screen in step with the first.

   Five screens carry the workflow: the list, intake, the Application context, the draft
   editor, and Ready.

   Validation, approval, and render are not among them. Each was a screen holding a single
   button, and each acted on the draft the editor was already showing, so reaching one
   meant leaving the text it described. They are now states of the editor: a panel, a
   dialog, and an inline step. Review joined them: the analysis it decides about is on the
   Application screen, so deciding on a separate route meant showing the subject in one
   place and the controls in another.

   Operation has no route. Queueing reports in place, so the screen was already off the
   workflow path; what kept it was the argument that an Operation outlives the screen that
   queued it and a direct link needs somewhere to land. It lands on the Application
   instead. The Operation screen's own content was the run's type, status, phase, message
   and failure - all of which `ActiveOperationPanel` shows on the screen that queued it -
   plus timestamps and identifiers, which are not shown anywhere now. */

/* `useParams` rather than a splat rewrite: the id is a path segment, and re-encoding it
   through the router is what keeps an id with a slash or a space landing where it did. */
const TrackingRedirect = () => {
  const { applicationId } = useParams();

  return (
    <Navigate
      replace
      to={`/applications/${encodeURIComponent(applicationId ?? "")}?view=tracking`}
    />
  );
};

const ReadyRedirect = () => {
  const { revisionId } = useParams();

  return <Navigate replace to={`/revisions/${encodeURIComponent(revisionId ?? "")}`} />;
};

export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    errorElement: <RouteErrorBoundary />,
    children: [
      {
        index: true,
        element: <ApplicationListPage />,
      },
      {
        /* Creating is one action taken from the list, not the thing the root does. */
        path: "applications/new",
        element: <NewApplicationPage />,
      },
      {
        /* The one destination for an existing Application, whether it was just created or
           opened from a duplicate. It is a fixed context screen rather than a redirect by
           stage: analysis is an action on it, not a screen of its own. */
        path: "applications/:applicationId",
        element: <ApplicationPage />,
        handle: { applicationContext: "self" },
      },
      {
        /* The recruitment axis used to be a route. Bookmarks and links to it are older
           than the merge, so the path stays and answers with the view it named. */
        path: "applications/:applicationId/tracking",
        element: <TrackingRedirect />,
      },
      {
        /* The draft editor: edit, preview, validate, approve, and render, on the one
           screen that holds the draft all five act on. */
        path: "applications/:applicationId/draft",
        element: <DraftEditorPage />,
      },
      {
        /* One approved revision, addressed by the revision itself. It stays a screen of
           its own rather than a state of the editor because the links that reach it -
           from the board and from the Application's action plan - name a specific
           immutable record, and an Application-keyed screen would answer them with
           whatever revision is current instead of the one named. */
        path: "revisions/:revisionId",
        element: <RevisionPage />,
      },
      {
        /* The address this screen had while it was named for the state rather than for
           the record it shows. */
        path: "approved-revisions/:revisionId/ready",
        element: <ReadyRedirect />,
      },
      {
        path: "settings",
        element: <SettingsPage />,
      },
      {
        path: "*",
        element: <RoutePlaceholder title="העמוד לא נמצא" />,
      },
    ],
  },
]);
