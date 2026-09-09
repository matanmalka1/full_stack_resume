import { Link, isRouteErrorResponse, useRouteError } from "react-router-dom";

import { ApiProblem } from "@/api/client";
import { buttonClasses } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { LtrText } from "@/ui/LtrText";
import { PageShell } from "@/ui/PageShell";
import { boardPath } from "../boardReturn";

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

const RouteErrorContent = ({ status }: { status: number | undefined }) => (
  <Card aria-labelledby="route-heading" role="alert">
    {status === undefined ? null : (
      <p className="text-support text-cv-text-muted">
        <LtrText>HTTP {status}</LtrText>
      </p>
    )}

    {/* A route failure leaves no useful action on its screen, so the shared presentation
        always carries one deterministic way back to the board. */}
    <div className={status === undefined ? undefined : "mt-4"}>
      <Link className={buttonClasses("primary")} to={boardPath()}>
        חזרה ללוח המועמדויות
      </Link>
    </div>
  </Card>
);

const RouteErrorPage = () => {
  const error = toSafeRouteError(useRouteError());

  return (
    <PageShell
      description={error.detail}
      eyebrow="הבקשה נכשלה"
      eyebrowTone="blocker"
      measure="form"
      title={error.title}
    >
      <RouteErrorContent status={error.status} />
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
