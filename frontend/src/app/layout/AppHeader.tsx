import { File, Plus } from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { cx } from "@/ui/cx";
import { SignOutButton } from "@/features/auth";
import { routePaths } from "@/navigation/routePaths";
import { AppNavigation, areaTitle } from "./AppNavigation";

/* The product's name, led by its mark: a page of a CV on the accent square. It links to
   the board, the area every visit starts from. */
const Brand = () => (
  <Link className="hidden min-w-0 items-center gap-2.5 rounded-control p-1 text-cv-text lg:flex" to={routePaths.home()}>
    <span
      aria-hidden="true"
      className="flex size-8.5 shrink-0 items-center justify-center rounded-control-sm bg-cv-accent text-cv-on-accent"
    >
      <File className="size-4.5" />
    </span>
    <span className="truncate text-body font-extrabold tracking-tight">סביבת קורות החיים</span>
  </Link>
);

/* Below the large breakpoint the top bar titles the screen, centred, as an iPhone's
   navigation bar does; the brand is the sidebar's alone. Decorative: the page's own
   heading is the one assistive tech reads, and saying it twice helps no one. */
const PhoneTitle = () => {
  const { pathname } = useLocation();

  return (
    <p aria-hidden="true" className="min-h-6 truncate text-body font-bold tracking-tight text-cv-text lg:hidden">
      {areaTitle(pathname) ?? "סביבת קורות החיים"}
    </p>
  );
};

/* One element, two shapes. From the large breakpoint it is the sidebar, top to bottom:
   the brand, the new-job command, the areas, and sign-out pinned to the foot. Below it,
   it is a top bar titling the screen (`PhoneTitle`), with the areas as a tab bar pinned to the bottom of the viewport (`AppNavigation`); the new-job
   command moves to the board's floating button and sign-out to Settings.

   `hiddenOnPhone` drops the whole header - top bar and tab bar, which lives inside it -
   below the large breakpoint, for a screen that brings its own. */
export const AppHeader = ({
  hiddenOnPhone = false,
  phoneBarSlotRef,
}: {
  hiddenOnPhone?: boolean;
  phoneBarSlotRef?: (element: HTMLDivElement | null) => void;
}) => {
  return (
    <header
      className={cx(
        "cv-glass-header sticky top-0 z-(--cv-z-navigation)",
        "lg:col-start-1 lg:row-start-1 lg:h-screen lg:border-e lg:border-cv-hairline lg:bg-cv-surface",
        hiddenOnPhone && "max-lg:hidden",
      )}
    >
      <div className="relative flex items-center justify-center gap-3 px-4 pt-4 pb-2 lg:h-full lg:flex-col lg:items-stretch lg:justify-start lg:gap-4 lg:py-5">
        <Brand />
        <PhoneTitle />
        {/* The trailing corner of the phone's bar, as an iPhone's navigation bar keeps
            one: a page whose title the bar already shows hands its commands here
            (`PageShell`'s `titleInPhoneBar`) rather than leaving them on a row alone. */}
        <div className="absolute inset-y-0 end-4 flex items-center gap-2 pt-2 lg:hidden" ref={phoneBarSlotRef} />

        {/* The wrapper carries the breakpoint: the link's own `inline-flex` and a `hidden`
            beside it would be settled by stylesheet order. */}
        <span className="hidden lg:flex">
          <Link
            aria-label="קליטת משרה חדשה"
            className="flex h-11 flex-1 items-center justify-center gap-1.5 rounded-control bg-cv-accent text-label font-bold text-cv-on-accent transition-colors hover:bg-cv-accent-hover"
            to={routePaths.newApplication}
          >
            <Plus aria-hidden="true" className="size-4.5" strokeWidth={2.25} />
            <span>משרה חדשה</span>
          </Link>
        </span>

        <AppNavigation />

        <span className="hidden lg:mt-auto lg:flex">
          <SignOutButton className="min-h-10 flex-1 justify-start gap-2.5 rounded-item px-3 text-label font-normal text-cv-text-muted hover:bg-cv-surface-muted hover:text-cv-text" />
        </span>
      </div>
    </header>
  );
};
