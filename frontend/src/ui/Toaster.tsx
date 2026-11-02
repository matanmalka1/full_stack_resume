import { X } from "lucide-react";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { IconButton } from "./IconButton";
import { type Toast, dismissToast, getToasts, subscribeToasts } from "./toast";

/* Long enough to read a title and one sentence; the clock stops while the pointer or
   focus is on the toast, so nobody has to read it against a clock they cannot pause. */
const TOAST_DURATION_MS = 6000;

const ToastItem = ({ toast }: { toast: Toast }) => {
  const [paused, setPaused] = useState(false);
  /* What is left of the clock, so a pause resumes where it stopped instead of starting
     the full duration over - the bar below drains on the same clock. */
  const remaining = useRef(TOAST_DURATION_MS);

  useEffect(() => {
    if (paused) return undefined;
    const startedAt = Date.now();
    const timer = window.setTimeout(() => dismissToast(toast.id), remaining.current);
    return () => {
      window.clearTimeout(timer);
      remaining.current -= Date.now() - startedAt;
    };
  }, [paused, toast.id]);

  return (
    /* The handlers only stop the clock; the toast's one control is its close button. */
    // oxlint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <li
      className="cv-toast-in pointer-events-auto relative overflow-hidden rounded-surface border border-cv-border bg-cv-surface shadow-floating"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setPaused(false);
      }}
      onFocus={() => setPaused(true)}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="flex items-start gap-3 py-3 ps-3.5 pe-1.5">
        <span
          aria-hidden="true"
          className="cv-toast-mark flex size-9 shrink-0 items-center justify-center rounded-pill bg-cv-accent text-cv-on-accent"
        >
          <svg
            className="size-4.5"
            fill="none"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={3}
            viewBox="0 0 24 24"
          >
            <path d="M5 12.5l4.5 4.5L19 7.5" />
          </svg>
        </span>
        <div className="min-w-0 flex-1 pt-1.5">
          <p className="text-body leading-6 font-bold text-cv-text" dir="auto">
            {toast.title}
          </p>
          {toast.body === undefined ? null : (
            <div className="mt-0.5 text-support leading-6 text-cv-text-muted" dir="auto">
              {toast.body}
            </div>
          )}
        </div>
        <IconButton
          aria-label="סגירת ההודעה"
          className="shrink-0 text-cv-text-muted hover:text-cv-text"
          onClick={() => dismissToast(toast.id)}
        >
          <X aria-hidden="true" className="size-icon-sm" />
        </IconButton>
      </div>
      {/* The time left, draining toward the close button; it stops with the clock. */}
      <span
        aria-hidden="true"
        className="cv-toast-timer absolute inset-x-0 bottom-0 h-0.5 bg-cv-accent"
        style={{ animationDuration: `${TOAST_DURATION_MS}ms`, animationPlayState: paused ? "paused" : "running" }}
      />
    </li>
  );
};

/* Every success message the application shows, in one corner: under the header on a
   phone, the top end corner on a wide screen (the sidebar holds the start side and the
   run panel the lower end corner). The live region is always mounted so a toast added
   to it is announced politely; it never takes focus. */
export const Toaster = () => {
  const toasts = useSyncExternalStore(subscribeToasts, getToasts, getToasts);

  return (
    <output
      aria-live="polite"
      className="pointer-events-none fixed inset-x-4 top-[4.5rem] z-(--cv-z-toast) lg:inset-x-auto lg:end-6 lg:top-6 lg:w-[22rem]"
    >
      <ol className="flex flex-col gap-2.5">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} />
        ))}
      </ol>
    </output>
  );
};
