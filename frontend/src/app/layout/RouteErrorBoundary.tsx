import { Link, isRouteErrorResponse, useRouteError } from "react-router-dom";

import { ApiProblem } from "@/api/client";
import { buttonClasses } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { LtrText } from "@/ui/LtrText";
import { PageHeading } from "@/ui/PageHeading";
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

export const RouteErrorBoundary = () => {
  const error = toSafeRouteError(useRouteError());

  return (
    /* A section rather than a `main` of its own: this renders in place of the screen,
       inside the shell's `main`, so a second one would nest two document landmarks. When
       the shell itself is what failed there is no outer landmark and this is the page. */
    <section className="page-frame px-6 py-12">
      <Card aria-labelledby="route-error-heading" role="alert">
        <PageHeading description={error.detail} eyebrow="הבקשה נכשלה" eyebrowTone="blocker" id="route-error-heading">
          {error.title}
        </PageHeading>
        {error.status === undefined ? null : (
          <p className="mt-4 text-support text-cv-text-muted">
            <LtrText>HTTP {error.status}</LtrText>
          </p>
        )}

        {/* The way out, for the same reason `NotFoundPage` carries one: a reader who lands
            here has nothing else on the screen to act on, and when the shell is what
            failed there is no navigation around this card either. */}
        <div className="mt-6">
          <Link className={buttonClasses("primary")} to={boardPath()}>
            חזרה ללוח המועמדויות
          </Link>
        </div>
      </Card>
    </section>
  );
};
