import { Link, Outlet } from "react-router-dom";

import { RouteFocusManager } from "./app/RouteFocusManager";
import { buttonClasses } from "./ui/Button";
import { type WorkflowStep, WorkflowSteps } from "./ui/WorkflowSteps";

/* Placeholder shape until the backend projection drives the landmark; the component
   already renders completed, current, and future stages. */
const workflowSteps: WorkflowStep[] = [
  { label: "משרה חדשה", state: "current" },
  { label: "ניתוח", state: "upcoming" },
  { label: "טיוטה", state: "upcoming" },
  { label: "אימות", state: "upcoming" },
  { label: "מוכן", state: "upcoming" },
];

export const App = () => {
  return (
    <div className="min-h-screen bg-cv-canvas text-cv-text">
      <RouteFocusManager />
      <header className="border-b border-cv-border bg-cv-surface">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-6 px-6">
          <Link className="rounded-control text-heading-sm font-semibold text-cv-text" to="/">
            סביבת קורות החיים
          </Link>
          <Link className={buttonClasses("secondary")} to="/settings">
            הגדרות
          </Link>
        </div>
      </header>

      <WorkflowSteps label="שלבי הכנת קורות החיים" steps={workflowSteps} />

      <main className="mx-auto max-w-5xl px-6 py-12">
        <Outlet />
      </main>
    </div>
  );
};
