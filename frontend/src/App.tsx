import { useQuery } from "@tanstack/react-query";
import { Settings } from "lucide-react";
import { Link, Outlet, useMatches } from "react-router-dom";

import { RouteFocusManager } from "./app/RouteFocusManager";
import { WorkflowLandmark, WorkflowLandmarkSteps } from "./app/WorkflowLandmark";
import { applicationDetailQueryOptions } from "./api/applications";
import { settingsQueryOptions } from "./api/settings";
import { buttonClasses } from "./ui/Button";

/* The Application named on the header line, and the way back to it.

   `href` is null on the Application screen itself, where a link would point at the page
   already showing it. Everywhere else it is the return path: the inner screens are three
   deep, and this is the only ancestor between them and the list. */
const ApplicationContext = ({
  company,
  href,
  targetRole,
}: {
  company: string;
  href: string | null;
  targetRole: string;
}) => {
  const body = (
    <>
      <span className="block truncate text-support font-bold text-cv-text" dir="auto">
        {company}
      </span>
      <span className="block truncate text-support text-cv-text-muted" dir="auto">
        {targetRole}
      </span>
    </>
  );

  return href === null ? (
    <div className="min-w-0 border-e border-cv-border pe-3 text-end">{body}</div>
  ) : (
    <Link className="min-w-0 rounded-control border-e border-cv-border pe-3 text-end hover:underline" to={href}>
      {body}
    </Link>
  );
};

export const App = () => {
  const settings = useQuery(settingsQueryOptions).data?.settings;
  const matches = useMatches();
  /* On the Application screen itself the context link would point at the page showing it.
     A link back to where you already are is not a way out, so the header states the
     Application without offering to navigate to it. The route declares that relationship
     in its handle; this shell does not match a named path to infer it. */
  const isApplicationScreen = matches.some(
    (match) => (match.handle as { applicationContext?: string } | undefined)?.applicationContext === "self",
  );
  const applicationId = matches.map((match) => match.params.applicationId).find((id) => id !== undefined) ?? null;
  const applicationContext = useQuery({
    ...applicationDetailQueryOptions(applicationId ?? ""),
    enabled: applicationId !== null,
  }).data?.application;

  return (
    <div
      className="min-h-screen text-cv-text"
      data-density={settings?.ui_density ?? "comfortable"}
      data-text-size={settings?.ui_text_size ?? "normal"}
    >
      <RouteFocusManager />
      <WorkflowLandmark>
        <header className="sticky top-0 z-30 border-b border-cv-border bg-cv-surface/85 backdrop-blur-xl">
          <div className="mx-auto flex min-h-16 max-w-[90rem] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2 sm:px-6 lg:px-8">
            {/* A wordmark rather than a logo tile: this is a local document tool, and
                the accent rule under the name does more to place it than a gradient
                square with a spark in it. */}
            <Link className="group shrink-0 rounded-control" to="/">
              <span className="block text-heading-sm font-extrabold tracking-tight text-cv-text">קורות חיים</span>
              <span className="block h-0.5 w-8 bg-cv-accent transition-all duration-200 group-hover:w-full" />
            </Link>

            <div className="ms-auto flex min-w-0 items-center gap-3">
              {/* Shown at every width. Hidden below `sm` it was absent exactly where a
                  back gesture is hardest to reach. */}
              {applicationContext === undefined || applicationId === null ? null : (
                <ApplicationContext
                  company={applicationContext.company}
                  href={isApplicationScreen ? null : `/applications/${encodeURIComponent(applicationId)}`}
                  targetRole={applicationContext.target_role}
                />
              )}
              <Link className={buttonClasses("ghost")} to="/settings">
                <Settings aria-hidden="true" className="size-4" />
                הגדרות
              </Link>
            </div>
          </div>
        </header>

        <main className="w-full px-4 py-5 sm:px-6 sm:py-6 lg:px-8">
          {/* `empty:hidden` removes the spacing on routes outside the CV workflow, where
              the landmark deliberately renders no steps. */}
          <div className="mx-auto mb-3 max-w-5xl empty:hidden sm:mb-4">
            <WorkflowLandmarkSteps />
          </div>
          <Outlet />
        </main>
      </WorkflowLandmark>
    </div>
  );
};
