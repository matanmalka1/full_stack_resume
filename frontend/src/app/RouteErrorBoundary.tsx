import { isRouteErrorResponse, useRouteError } from "react-router-dom";

import { ApiProblem } from "../api/client";
import { Card } from "../ui/Card";
import { LtrText } from "../ui/LtrText";
import { PageHeading } from "../ui/PageHeading";

interface SafeRouteError {
  title: string;
  detail: string;
  status?: number;
}

const toSafeRouteError = (error: unknown): SafeRouteError => {
  if (error instanceof ApiProblem) {
    return {
      title: error.problem.title,
      detail: error.problem.detail,
      status: error.problem.status,
    };
  }

  if (isRouteErrorResponse(error)) {
    return {
      title: "לא ניתן לפתוח את העמוד",
      detail: "העמוד המבוקש אינו זמין כרגע.",
      status: error.status,
    };
  }

  return {
    title: "אירעה שגיאה",
    detail: "לא ניתן להשלים את הפעולה. אפשר לנסות שוב.",
  };
};

export const RouteErrorBoundary = () => {
  const error = toSafeRouteError(useRouteError());

  return (
    <main className="mx-auto max-w-5xl px-6 py-12" dir="rtl">
      <Card aria-labelledby="route-error-heading" role="alert">
        <PageHeading description={error.detail} eyebrow="הבקשה נכשלה" eyebrowTone="blocker" id="route-error-heading">
          {error.title}
        </PageHeading>
        {error.status === undefined ? null : (
          <p className="mt-4 text-support text-cv-text-muted">
            <LtrText>HTTP {error.status}</LtrText>
          </p>
        )}
      </Card>
    </main>
  );
};
