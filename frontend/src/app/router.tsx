import { createBrowserRouter } from "react-router-dom";

import { App } from "../App";
import { ApplicationListPage } from "../pages/ApplicationListPage";
import { ApplicationPage } from "../pages/ApplicationPage";
import { DraftEditorPage } from "../pages/DraftEditorPage";
import { NewApplicationPage } from "../pages/NewApplicationPage";
import { OperationPage } from "../pages/OperationPage";
import { ReadyPage } from "../pages/ReadyPage";
import { RoutePlaceholder } from "../pages/RoutePlaceholder";
import { SettingsPage } from "../pages/SettingsPage";
import { TrackingPage } from "../pages/TrackingPage";
import { RouteErrorBoundary } from "./RouteErrorBoundary";

/* The root is the Application list, and intake is a screen reached from it. The two were
   the other way round until the list existed at all: with the form at `/`, the wordmark
   started a new Application instead of going home, and a saved one was reachable only by
   its URL or the back button.

   Recruitment tracking is a sixth screen, off the workflow path: it is the Application's
   other axis, switched to from the preparation view rather than reached through it.

   Five screens carry the workflow: the list, intake, the Application context, the draft
   editor, and Ready.

   Validation, approval, and render are not among them. Each was a screen holding a single
   button, and each acted on the draft the editor was already showing, so reaching one
   meant leaving the text it described. They are now states of the editor: a panel, a
   dialog, and an inline step. Review joined them: the analysis it decides about is on the
   Application screen, so deciding on a separate route meant showing the subject in one
   place and the controls in another.

   Operation keeps its route. It is not on the workflow path any more - queueing reports
   in place - but an Operation outlives the screen that queued it, so a direct link, a
   bookmark, or a reload has somewhere to land. */
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
      },
      {
        /* The recruitment axis of the same Application. It is a second view rather than a
           panel on the first because the two axes are independent: preparation is about
           the document, tracking is about the recruiter, and neither state answers the
           other. Sharing one card made every visit start by working out which of the two
           the screen was reporting. */
        path: "applications/:applicationId/tracking",
        element: <TrackingPage />,
      },
      {
        path: "operations/:operationId",
        element: <OperationPage />,
      },
      {
        /* The draft editor: edit, preview, validate, approve, and render, on the one
           screen that holds the draft all five act on. */
        path: "applications/:applicationId/draft",
        element: <DraftEditorPage />,
      },
      {
        path: "approved-revisions/:approvedRevisionId/ready",
        element: <ReadyPage />,
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
