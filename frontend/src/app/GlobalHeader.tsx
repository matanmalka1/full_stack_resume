import { Plus, Search, Settings } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { buttonClasses } from "../ui/Button";
import { Tooltip } from "../ui/Tooltip";
import { ApplicationQuickSwitcher } from "./ApplicationQuickSwitcher";
import { appRoutes } from "./appRoutes";
import { GlobalSearchDialog } from "./GlobalSearchDialog";

const isTypingTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
};

const SearchTriggerButton = ({ onClick }: { onClick: () => void }) => (
  <button
    aria-label="חיפוש מהיר של מועמדויות (Cmd+K)"
    className="inline-flex items-center gap-2 rounded-control border border-cv-border bg-cv-surface-muted px-3 py-1.5 text-support text-cv-text-muted transition-colors hover:border-cv-border-strong hover:bg-cv-surface hover:text-cv-text"
    onClick={onClick}
    type="button"
  >
    <Search aria-hidden="true" className="size-4 shrink-0 text-cv-accent" />
    <span className="hidden md:inline">חיפוש מהיר…</span>
    <kbd className="hidden rounded border border-cv-border bg-cv-surface px-1.5 py-0.5 text-support font-mono text-cv-text-muted sm:inline-block">
      ⌘K
    </kbd>
  </button>
);

export const GlobalHeader = () => {
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && (event.key === "k" || event.key === "K")) {
        /* Typing "k" while composing text (with the modifier held incidentally, e.g. some
           IME or emoji-picker chords) should not steal focus into the dialog. */
        if (isTypingTarget(event.target)) {
          return;
        }
        event.preventDefault();
        setSearchOpen((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-cv-border bg-cv-surface/85 backdrop-blur-xl">
        <div className="page-frame flex min-h-16 flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-2 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-4 sm:gap-6">
            <Link className="group shrink-0 rounded-control" to={appRoutes.home}>
              <span className="block text-heading-sm font-extrabold tracking-tight text-cv-text">קורות חיים</span>
              <span className="block h-0.5 w-8 bg-cv-accent transition-all duration-200 group-hover:w-full" />
            </Link>

            <div className="hidden h-5 w-px bg-cv-border sm:block" />

            <ApplicationQuickSwitcher />
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <SearchTriggerButton onClick={() => setSearchOpen(true)} />

            <Tooltip label="קליטת משרה חדשה">
              <Link className={buttonClasses("primary", "py-1.5 px-3 text-support")} to={appRoutes.newApplication}>
                <Plus aria-hidden="true" className="size-4" />
                <span className="hidden sm:inline">משרה חדשה</span>
              </Link>
            </Tooltip>

            <div className="hidden h-5 w-px bg-cv-border sm:block" />

            <Tooltip label="הגדרות המערכת">
              <Link aria-label="הגדרות המערכת" className={buttonClasses("ghost", "p-2")} to={appRoutes.settings}>
                <Settings aria-hidden="true" className="size-4 text-cv-text-muted hover:text-cv-text" />
              </Link>
            </Tooltip>
          </div>
        </div>
      </header>

      <GlobalSearchDialog onClose={() => setSearchOpen(false)} open={searchOpen} />
    </>
  );
};
