import { useIsFetching } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { buttonClasses } from "@/ui/Button";
import { GlobalSearch } from "../search/GlobalSearch";
import { boardPath } from "../boardReturn";
import { routePaths } from "../routePaths";
import { AppNavigation } from "./AppNavigation";
import { ThemeToggle } from "./ThemeToggle";

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
    <span
      aria-hidden="true"
      className="absolute inset-x-0 bottom-0 h-0.5 bg-cv-accent motion-safe:animate-pulse lg:fixed lg:inset-x-0 lg:top-0 lg:bottom-auto lg:z-(--cv-z-toast)"
    />
  );
};
export const AppHeader = () => {
  return (
    <header className="sticky top-0 z-(--cv-z-navigation) border-b border-cv-hairline bg-cv-canvas/90 backdrop-blur-xl lg:col-start-1 lg:row-start-1 lg:h-screen lg:border-b-0 lg:border-e lg:bg-cv-canvas lg:backdrop-blur-none">
      <div className="page-gutter lg:flex lg:h-full lg:flex-col lg:px-4 lg:py-5">
        <div className="page-frame flex min-h-16 flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2 lg:mx-0 lg:min-h-0 lg:w-full lg:flex-1 lg:flex-col lg:items-stretch lg:justify-start lg:gap-6 lg:py-0">
          <div className="flex min-w-0 items-center gap-4 sm:gap-6 lg:flex-col lg:items-stretch lg:gap-6">
            <Link className="group shrink-0 rounded-control" to={boardPath()}>
              <span className="block text-heading-sm font-extrabold tracking-tight text-cv-text">קורות חיים</span>
              <span className="block h-0.5 w-8 bg-cv-accent transition-all duration-200 group-hover:w-full" />
            </Link>

            <div className="hidden h-5 w-px bg-cv-hairline sm:block lg:hidden" />
            <AppNavigation />
          </div>

          {/* In the sidebar this wraps into exactly two rows: the palette takes the
              column's full width - it is the one control here with a label to read - and
              the new-job command shares the row below it with the theme toggle. Left to
              free wrapping at a 15rem measure each control claimed a row of its own, and
              the toggle, the only one narrower than the column, sat alone against the
              opening edge reading as a stray control rather than as part of the group. */}
          <div className="flex items-center gap-2 sm:gap-3 lg:mt-auto lg:flex-wrap lg:gap-2">
            <GlobalSearch className="lg:w-full" showTrigger />

            <Link
              aria-label="קליטת משרה חדשה"
              className={buttonClasses("primary", "lg:min-h-11 lg:flex-1", "compact")}
              to={routePaths.newApplication}
            >
              <Plus aria-hidden="true" className="size-icon-md" />
              <span className="hidden sm:inline">משרה חדשה</span>
            </Link>

            <ThemeToggle />
          </div>
        </div>
      </div>

      <GlobalActivityBar />
    </header>
  );
};
