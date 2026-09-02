import { Navigate, createBrowserRouter, useParams } from "react-router-dom";

import { App } from "../App";
import { ApplicationListPage } from "../pages/ApplicationListPage";
import { ApplicationPage } from "../pages/ApplicationPage";
import { JobDetailsPage } from "../pages/JobDetailsPage";
import { DraftEditorPage } from "../pages/draft-editor/DraftEditorPage";
import { NewApplicationPage } from "../pages/NewApplicationPage";
import { RevisionPage } from "../pages/RevisionPage";
import { RoutePlaceholder } from "../pages/RoutePlaceholder";
import { SettingsPage } from "../pages/SettingsPage";
import { appRoutes } from "./appRoutes";
import { RouteErrorBoundary } from "./RouteErrorBoundary";

/* The root is the Application list, and intake is a screen reached from it. The two were
   the other way round until the list existed at all: with the form at `/`, the wordmark
   started a new Application instead of going home, and a saved one was reachable only by
   its URL or the back button.

   Job Detail owns recruitment tracking and the posting. CV preparation is a separate
   destination under the same Application and continues to own the document workflow.

   Six screens carry the workflow: the list, intake, Job Detail, CV preparation, the
   draft editor, and Ready.

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

  return <Navigate replace to={appRoutes.application(applicationId ?? "")} />;
};

const ReadyRedirect = () => {
  const { revisionId } = useParams();

  return <Navigate replace to={appRoutes.revision(revisionId ?? "")} />;
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
        /* The stable destination for an existing Application: its job facts, recruitment
           history, preparation summary, and immutable outputs. */
        path: "applications/:applicationId",
        element: <JobDetailsPage />,
        handle: { applicationContext: "self" },
      },
      {
        /* The document workflow is addressed separately from the job record. */
        path: "applications/:applicationId/preparation",
        element: <ApplicationPage />,
      },
      {
        /* Recruitment now lives on Job Detail. The path remains for old bookmarks. */
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
