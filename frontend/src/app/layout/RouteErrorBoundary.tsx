import { useEffect } from "react";
import { Link, isRouteErrorResponse, useRouteError } from "react-router-dom";

import { buttonClasses } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { problemSentence } from "@/ui/errorMessages";
import { PageShell } from "@/ui/PageShell";
import { reportError } from "@/ui/reportError";
import { boardPath } from "@/navigation/boardReturn";

interface SafeRouteError {
  title: string;
  detail: string;
}

/* The reader's copy only. The status, the server's prose, and any exception text are
   diagnostics: `reportError` keeps them in the console. */
const toSafeRouteError = (error: unknown): SafeRouteError => {
  if (isRouteErrorResponse(error)) {
    return {
      title: "לא ניתן לפתוח את העמוד",
      detail: "העמוד המבוקש אינו זמין כרגע. אפשר לחזור ללוח המועמדויות.",
    };
  }

  return {
    title: "לא ניתן להציג את העמוד",
    detail: problemSentence(error, "אירעה שגיאה בלתי צפויה. אפשר לרענן את העמוד או לחזור ללוח המועמדויות."),
  };
};

const RouteErrorContent = () => (
  <Card aria-labelledby="route-heading" role="alert">
    {/* A route failure leaves no useful action on its screen, so the shared presentation
        always carries one deterministic way back to the board. */}
    <Link className={buttonClasses("primary")} to={boardPath()}>
      חזרה ללוח המועמדויות
    </Link>
  </Card>
);

const RouteErrorPage = () => {
  const routeError = useRouteError();
  useEffect(() => {
    reportError("route_error", isRouteErrorResponse(routeError) ? { status: routeError.status } : routeError);
  }, [routeError]);
  const error = toSafeRouteError(routeError);

  return (
    <PageShell description={error.detail} eyebrow="תקלה" eyebrowTone="blocker" measure="form" title={error.title}>
      <RouteErrorContent />
    </PageShell>
  );
};

/* A screen failure replaces the Outlet inside AppLayout, whose main landmark and gutter
   remain in place. */
export const RouteErrorBoundary = RouteErrorPage;

/* A layout failure has no outer document container left. Supply only those missing
   responsibilities, then render the exact same error page presentation. */
export const RootRouteErrorBoundary = () => (
  <main className="page-gutter py-12">
    <RouteErrorPage />
  </main>
);
