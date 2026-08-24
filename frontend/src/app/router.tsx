import { createBrowserRouter } from "react-router-dom";

import { App } from "../App";
import { ApplicationPage } from "../pages/ApplicationPage";
import { DraftEditorPage } from "../pages/DraftEditorPage";
import { NewApplicationPage } from "../pages/NewApplicationPage";
import { OperationPage } from "../pages/OperationPage";
import { ApprovalPage } from "../pages/ApprovalPage";
import { ReadyPage } from "../pages/ReadyPage";
import { RenderPage } from "../pages/RenderPage";
import { ReviewPage } from "../pages/ReviewPage";
import { RoutePlaceholder } from "../pages/RoutePlaceholder";
import { SettingsPage } from "../pages/SettingsPage";
import { ValidationPage } from "../pages/ValidationPage";
import { RouteErrorBoundary } from "./RouteErrorBoundary";

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
        path: "applications/:applicationId/draft",
        element: <DraftEditorPage />,
      },
      {
        path: "applications/:applicationId/validation",
        element: <ValidationPage />,
      },
      {
        path: "applications/:applicationId/approval",
        element: <ApprovalPage />,
      },
      {
        path: "approved-revisions/:approvedRevisionId/render",
        element: <RenderPage />,
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
