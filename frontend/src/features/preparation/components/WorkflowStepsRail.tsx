import { Fragment } from "react";

import { Check, ChevronLeft } from "lucide-react";
import { Link } from "react-router-dom";

import { cx } from "@/ui/cx";

type WorkflowStepState = "complete" | "current" | "upcoming";

export interface WorkflowStep {
  here?: boolean;
  href?: string;
  label: string;
  state: WorkflowStepState;
}

interface WorkflowStepsRailProps {
  label: string;
  steps: WorkflowStep[];
}

/* No `overflow-hidden`. It was there to keep the corners clean, but with the row inside it
   set to scroll, what it actually did was cut the flow's last steps off the frame at the
   widths this screen is read at. Nothing here is positioned outside the box, so the corners
   survive without it. */
const railClasses =
  "w-full min-w-0 rounded-control border border-cv-border bg-cv-surface px-3 py-4 shadow-surface sm:px-4";

const stepMarkClasses: Record<WorkflowStepState, string> = {
  complete: "border-cv-success/25 bg-cv-success-soft text-cv-success",
  current: "border-cv-accent bg-cv-accent text-cv-on-accent",
  upcoming: "border-cv-border bg-cv-surface text-cv-text-muted",
};

const stepLabelClasses: Record<WorkflowStepState, string> = {
  complete: "font-semibold text-cv-text",
  current: "font-bold text-cv-accent",
  upcoming: "font-medium text-cv-text-muted",
};

const connectorClasses: Record<WorkflowStepState, string> = {
  complete: "bg-cv-success",
  current: "bg-cv-accent",
  upcoming: "workflow-track-upcoming",
};

const StepMark = ({ index, state }: { index: number; state: WorkflowStepState }) => (
  <span
    aria-hidden="true"
    className={cx(
      "relative z-(--cv-z-content-raised) flex size-8 shrink-0 items-center justify-center rounded-pill border",
      "text-support font-bold transition-[background-color,border-color,color] duration-200",
      stepMarkClasses[state],
    )}
  >
    {state === "complete" ? <Check className="size-icon-md [stroke-width:var(--stroke-icon-strong)]" /> : index + 1}
  </span>
);

/* One step: a mark and its label, the whole rail's only content. The state used to carry
   its own caption underneath ("הושלם" / "בתהליך" / "בהמשך") - a second line that made a
   navigational rail read as a content section three rows tall. It was never the only
   place that information lived: a `Link`'s own accessible name already says "חזרה" or
   "מעבר" from its position relative to the open screen, and `aria-current="step"` marks
   the current one, so the caption was sighted users' only source for a fact assistive
   tech already had another way to reach. What remains carries the same three states in
   the mark's own shape (a check, a filled circle, an outline) and in the label's weight
   and colour - color is never the only signal (A.2), and it no longer needs to be a
   second line to avoid being one. */
const StepBody = ({ index, step }: { index: number; step: WorkflowStep }) => (
  <span
    className={cx(
      /* Tightens rather than truncates: below the wide breakpoints the padding and the gap
         between mark and label give up their room first, so the words themselves never
         have to. */
      "relative flex min-w-0 flex-1 items-center gap-3 px-2 py-2 text-heading-sm transition-colors duration-200",
      stepLabelClasses[step.state],
      step.state === "current" && "font-bold",
    )}
  >
    <StepMark index={index} state={step.state} />
    <span className="min-w-0 flex-1 whitespace-nowrap">{step.label}</span>
    {step.href === undefined ? null : (
      <ChevronLeft
        aria-hidden="true"
        className="size-icon-md shrink-0 text-cv-text-muted transition-transform duration-200 group-hover:-translate-x-0.5 group-hover:text-cv-accent"
      />
    )}
  </span>
);

/* The workflow's route-level axis. `PageShell` places it beside the active stage content
   on wide screens; here it owns the large marks, labels and continuous vertical line.
   On narrow screens the same landmark stacks above the content without changing its
   order or accessible description. */
export const WorkflowStepsRail = ({ label, steps }: WorkflowStepsRailProps) => {
  const current = steps.find((step) => step.state === "current");
  const position = current === undefined ? null : steps.indexOf(current) + 1;
  const completed = current === undefined && steps.length > 0 && steps.every((step) => step.state === "complete");
  const here = steps.find((step) => step.here === true);
  const hereIndex = steps.findIndex((step) => step.here === true);
  const elsewhere = here !== undefined && here !== current;

  const spoken = completed
    ? `הושלם, ${steps.length} מתוך ${steps.length}`
    : position === null
      ? null
      : `שלב ${position} מתוך ${steps.length}, ${current?.label}`;

  const description =
    spoken === null
      ? here === undefined
        ? label
        : `${label}: העמוד הפתוח ${here.label}`
      : `${label}: ${spoken}${elsewhere ? `. העמוד הפתוח: ${here.label}` : ""}`;

  const navigable = steps.some((step) => step.href !== undefined);

  /* Led by a Hebrew word rather than a bare digit. Two number runs with nothing but
     Hebrew between them still read correctly in an RTL paragraph, but a number run at
     the very start of one does not carry the paragraph's own direction the way a Hebrew
     word does - left as `"2 מתוך 3"` with no anchor before the "2", browsers have shown
     the pair transposed ("3 מתוך 2"). A leading word fixes the embedding, same as the
     screen-reader sentence above already has one. */
  const progressText = completed
    ? `הושלם ${steps.length} מתוך ${steps.length}`
    : position === null
      ? null
      : `שלב ${position} מתוך ${steps.length}`;

  const content = (
    <div className="flex flex-col gap-4">
      {/* Decorative: the nav's own `aria-label` already states the label and the
          position in words, so this repeats it for sighted readers only. */}
      <div aria-hidden="true" className="flex shrink-0 flex-wrap items-baseline gap-x-2">
        <span className="text-heading-sm font-bold text-cv-text">{label}</span>
        {/* The count never breaks across lines. Beside a two-line label in the 13rem
            spine column there is room for about half of it, and the wrap fell inside the
            phrase - "הושלם 4" over "מתוך 4" - which reads as two numbers rather than one
            ratio. Held together it drops to its own line instead. */}
        {progressText === null ? null : (
          <span className="text-caption whitespace-nowrap text-cv-text-muted">{progressText}</span>
        )}
      </div>

      {/* Every step, always drawn. This used to be a bar-less horizontal scroller, on the
          reasoning that the keyboard reaches each step in order anyway - but a sighted
          reader has no way to know a stage exists past the edge of a strip that shows no
          scrollbar, and the spine's whole job is to say where the work stands across all
          four.

          From the large breakpoint up the row holds its width and never breaks: the
          padding, the gaps and the connectors tighten instead. Below that - a phone, a
          split window - a second line is better than a row running off the frame, so the
          row may shrink and wrap again. */}
      <div className="min-w-0">
        <div className="flex flex-col">
          {steps.map((step, index) => {
            const body = <StepBody index={index} step={step} />;
            const next = steps[index + 1];

            return (
              <Fragment key={step.label}>
                {step.href === undefined ? (
                  <div
                    aria-hidden="true"
                    className={cx(
                      "flex w-full rounded-control border border-transparent",
                      step.here === true && "border-cv-accent/25 bg-cv-accent-soft",
                    )}
                  >
                    {body}
                  </div>
                ) : (
                  <Link
                    aria-current={step.state === "current" ? "step" : undefined}
                    aria-label={
                      completed && index === steps.length - 1
                        ? `פתיחת שלב ${step.label}`
                        : `${hereIndex !== -1 && index < hereIndex ? "חזרה" : "מעבר"} לשלב ${step.label}`
                    }
                    className={cx(
                      "group flex min-h-12 w-full items-center rounded-control border border-transparent",
                      "transition-[background-color,border-color,box-shadow] duration-200",
                      "hover:border-cv-border hover:bg-cv-surface-muted",
                      step.here === true && "border-cv-accent/25 bg-cv-accent-soft",
                    )}
                    to={step.href}
                  >
                    {body}
                  </Link>
                )}

                {next === undefined ? null : (
                  <span
                    aria-hidden="true"
                    className={cx("ms-[1.45rem] h-5 w-px shrink-0", connectorClasses[next.state])}
                  />
                )}
              </Fragment>
            );
          })}
        </div>
      </div>
    </div>
  );

  if (!navigable) {
    return (
      // The rail's real elements are exposed via aria-hidden; role="img" presents the
      // composite as one image for assistive tech, which `<img>` (a void element) cannot do.
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      <div aria-label={description} className={railClasses} role="img">
        <div aria-hidden="true">{content}</div>
      </div>
    );
  }

  return (
    <nav aria-label={description} className={railClasses}>
      {content}
    </nav>
  );
};
