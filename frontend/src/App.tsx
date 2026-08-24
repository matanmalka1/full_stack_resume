const workflowSteps = ["משרה חדשה", "ניתוח", "טיוטה", "אימות", "מוכן"];

export function App() {
  return (
    <div className="min-h-screen bg-cv-canvas text-cv-text">
      <header className="border-b border-cv-border bg-cv-surface">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-6 px-6">
          <a
            className="rounded-sm text-lg font-semibold text-cv-text outline-none focus-visible:ring-2 focus-visible:ring-cv-focus focus-visible:ring-offset-2"
            href="/"
          >
            סביבת קורות החיים
          </a>
          <button
            className="min-h-11 rounded-md border border-cv-border bg-cv-surface px-4 text-sm font-medium text-cv-text outline-none hover:bg-cv-surface-muted focus-visible:ring-2 focus-visible:ring-cv-focus focus-visible:ring-offset-2"
            type="button"
          >
            הגדרות
          </button>
        </div>
      </header>

      <nav
        aria-label="שלבי הכנת קורות החיים"
        className="border-b border-cv-border bg-cv-surface"
      >
        <ol className="mx-auto flex max-w-7xl gap-2 overflow-x-auto px-6 py-3 text-sm">
          {workflowSteps.map((step, index) => (
            <li
              aria-current={index === 0 ? "step" : undefined}
              className={
                index === 0
                  ? "shrink-0 rounded-md bg-cv-accent-soft px-3 py-2 font-semibold text-cv-accent"
                  : "shrink-0 px-3 py-2 text-cv-text-muted"
              }
              key={step}
            >
              {step}
            </li>
          ))}
        </ol>
      </nav>

      <main className="mx-auto max-w-5xl px-6 py-12">
        <section
          aria-labelledby="foundation-heading"
          className="rounded-xl border border-cv-border bg-cv-surface p-8"
        >
          <p className="mb-2 text-sm font-semibold text-cv-accent">M4 · תשתית הממשק</p>
          <h1 className="text-3xl font-semibold tracking-tight" id="foundation-heading">
            סביבת העבודה מוכנה לבניית התהליך
          </h1>
          <p className="mt-4 max-w-2xl leading-7 text-cv-text-muted">
            מעטפת React בעברית הוגדרה. מסך יצירת המועמדות והחיבור ל־API יתווספו בשלבים
            הבאים.
          </p>
        </section>
      </main>
    </div>
  );
}
