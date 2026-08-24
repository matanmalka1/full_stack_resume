import { createBrowserRouter } from "react-router-dom";

import { App } from "../App";
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
        element: (
          <RoutePlaceholder
            description="מעטפת React בעברית הוגדרה. מסך יצירת המועמדות והחיבור ל־API יתווספו בשלבים הבאים."
            title="סביבת העבודה מוכנה לבניית התהליך"
          />
        ),
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
