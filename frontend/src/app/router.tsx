import { createBrowserRouter } from "react-router-dom";

import { App } from "../App";
import { NewApplicationPage } from "../pages/NewApplicationPage";
import { OperationPage } from "../pages/OperationPage";
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
        /* Where an existing duplicate is opened. The screen that reads the application
           projection arrives with the Stage C continuation; until then the route exists
           so the choice is a real destination rather than a dead link. */
        path: "applications/:applicationId",
        element: <RoutePlaceholder title="מועמדות קיימת" />,
      },
      {
        path: "applications/:applicationId/analysis",
        element: <RoutePlaceholder title="ניתוח המשרה" />,
      },
      {
        path: "operations/:operationId",
        element: <OperationPage />,
      },
      {
        path: "applications/:applicationId/review",
        element: <RoutePlaceholder title="סקירת הניתוח" />,
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
