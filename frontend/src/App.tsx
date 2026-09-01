import { useQuery } from "@tanstack/react-query";
import { Settings } from "lucide-react";
import { Link, Outlet, useMatches } from "react-router-dom";

import { RouteFocusManager } from "./app/RouteFocusManager";
import { WorkflowLandmark, WorkflowLandmarkSteps } from "./app/WorkflowLandmark";
import { applicationDetailQueryOptions } from "./api/applications";
import { settingsQueryOptions } from "./api/settings";
import { buttonClasses } from "./ui/Button";

/* The Application named on an inner screen's header line, and the way back to Job Detail. */
const ApplicationContext = ({ company, href, targetRole }: { company: string; href: string; targetRole: string }) => {
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

  return (
    <Link className="min-w-0 rounded-control border-e border-cv-border pe-3 text-end hover:underline" to={href}>
      {body}
    </Link>
  );
};

export const App = () => {
  const settings = useQuery(settingsQueryOptions).data?.settings;
  const matches = useMatches();
  /* Job Detail names the company and role in its own content, so repeating the same pair
     in the shell would make the new owner look duplicated. Inner screens keep the pair as
     their link back to Job Detail. The route declares that relationship in its handle. */
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
          <div className="page-frame flex min-h-16 flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2 sm:px-6 lg:px-8">
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
              {applicationContext === undefined || applicationId === null || isApplicationScreen ? null : (
                <ApplicationContext
                  company={applicationContext.company}
                  href={`/applications/${encodeURIComponent(applicationId)}`}
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

          <div className="page-frame mb-3 empty:hidden sm:mb-4">
            <WorkflowLandmarkSteps />
          </div>
          <Outlet />
        </main>
      </WorkflowLandmark>
    </div>
  );
};
