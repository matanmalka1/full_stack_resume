import { useEffect, useRef } from "react";
import { isRouteErrorResponse, useRouteError } from "react-router-dom";

import { ApiProblem } from "../api/client";

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
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12" dir="rtl">
      <section
        aria-labelledby="route-error-heading"
        className="rounded-xl border border-cv-border bg-cv-surface p-8"
        role="alert"
      >
        <p className="mb-2 text-sm font-semibold text-cv-blocker">הבקשה נכשלה</p>
        <h1
          className="text-3xl font-semibold tracking-tight outline-none"
          data-route-heading
          id="route-error-heading"
          ref={headingRef}
          tabIndex={-1}
        >
          {error.title}
        </h1>
        <p className="mt-4 max-w-2xl leading-7 text-cv-text-muted">{error.detail}</p>
        {error.status === undefined ? null : (
          <p className="mt-4 text-sm text-cv-text-muted" dir="ltr">
            HTTP {error.status}
          </p>
        )}
      </section>
    </main>
  );
};
