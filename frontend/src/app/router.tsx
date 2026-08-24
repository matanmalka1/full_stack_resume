import { createBrowserRouter } from "react-router-dom";

import { App } from "../App";
import { ApplicationPage } from "../pages/ApplicationPage";
import { NewApplicationPage } from "../pages/NewApplicationPage";
import { OperationPage } from "../pages/OperationPage";
import { ReviewPage } from "../pages/ReviewPage";
import { RoutePlaceholder } from "../pages/RoutePlaceholder";
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
        element: <RoutePlaceholder title="עריכת הטיוטה" />,
      },
      {
        path: "applications/:applicationId/validation",
        element: <RoutePlaceholder title="תוצאות האימות" />,
      },
      {
        path: "applications/:applicationId/approval",
        element: <RoutePlaceholder title="אישור הגרסה" />,
      },
      {
        path: "approved-revisions/:approvedRevisionId/render",
        element: <RoutePlaceholder title="יצירת קובץ קורות החיים" />,
      },
      {
        path: "approved-revisions/:approvedRevisionId/ready",
        element: <RoutePlaceholder title="קורות החיים מוכנים" />,
      },
      {
        path: "settings",
        element: <RoutePlaceholder title="הגדרות" />,
      },
      {
        path: "*",
        element: <RoutePlaceholder title="העמוד לא נמצא" />,
      },
    ],
  },
]);
