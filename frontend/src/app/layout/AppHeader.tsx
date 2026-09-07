import { useIsFetching } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { buttonClasses } from "@/ui/Button";
import { Tooltip } from "@/ui/Tooltip";
import { GlobalSearch } from "../search/GlobalSearch";
import { routePaths } from "../routePaths";
import { AppNavigation } from "./AppNavigation";

/* Whether the application is currently talking to the server, anywhere. Decorative: the
   screens announce their own loading in words through `QueryState`, and a bar that also
   spoke would say it a second time on every refetch. This one answers the same question
   at a glance, in the one place that is on screen on every route. */
const GlobalActivityBar = () => {
  const fetching = useIsFetching();

  if (fetching === 0) {
    return null;
  }

  return (
    <span aria-hidden="true" className="absolute inset-x-0 bottom-0 h-0.5 bg-cv-accent motion-safe:animate-pulse" />
  );
};

/* The shell masthead: where the reader is (primary navigation), how to get anywhere
   (the wordmark and the search palette), and the one action that is global rather than
   any page's - starting a new Application.
   
   It knows nothing about the record on screen. An Application names itself in its own
   breadcrumbs and heading, and the header carrying a second copy of that made the
   record's identity a shell concern. */
export const AppHeader = () => (
  <header className="sticky top-0 z-30 border-b border-cv-border bg-cv-surface/85 backdrop-blur-xl">
    <div className="page-frame flex min-h-16 flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-2 sm:px-6 lg:px-8">
      <div className="flex min-w-0 items-center gap-4 sm:gap-6">
        <Link className="group shrink-0 rounded-control" to={routePaths.home}>
          <span className="block text-heading-sm font-extrabold tracking-tight text-cv-text">קורות חיים</span>
          <span className="block h-0.5 w-8 bg-cv-accent transition-all duration-200 group-hover:w-full" />
        </Link>

        <div className="hidden h-5 w-px bg-cv-border sm:block" />

        <AppNavigation />
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        <GlobalSearch />

        <Tooltip label="קליטת משרה חדשה">
          <Link
            aria-label="קליטת משרה חדשה"
            className={buttonClasses("primary", "py-1.5 px-3 text-support")}
            to={routePaths.newApplication}
          >
            <Plus aria-hidden="true" className="size-4" />
            <span className="hidden sm:inline">משרה חדשה</span>
          </Link>
        </Tooltip>
      </div>
    </div>

    <GlobalActivityBar />
  </header>
);
