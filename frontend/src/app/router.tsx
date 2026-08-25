import { createBrowserRouter } from "react-router-dom";

import { App } from "../App";
import { ApplicationPage } from "../pages/ApplicationPage";
import { DraftEditorPage } from "../pages/DraftEditorPage";
import { NewApplicationPage } from "../pages/NewApplicationPage";
import { OperationPage } from "../pages/OperationPage";
import { ReadyPage } from "../pages/ReadyPage";
import { ReviewPage } from "../pages/ReviewPage";
import { RoutePlaceholder } from "../pages/RoutePlaceholder";
import { SettingsPage } from "../pages/SettingsPage";
import { RouteErrorBoundary } from "./RouteErrorBoundary";

/* Four screens carry the workflow: intake, the Application context, the draft editor,
   and Ready.

   Validation, approval, and render are not among them. Each was a screen holding a single
   button, and each acted on the draft the editor was already showing, so reaching one
   meant leaving the text it described. They are now states of the editor: a panel, a
   dialog, and an inline step. Review and Operation keep their own routes because each has
   something of its own to show - a decision form, and durable progress that outlives the
   screen that queued it. */
export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    errorElement: <RouteErrorBoundary />,
    children: [
      {
        index: true,
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
        path: "operations/:operationId",
        element: <OperationPage />,
      },
      {
        path: "applications/:applicationId/review",
        element: <ReviewPage />,
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
