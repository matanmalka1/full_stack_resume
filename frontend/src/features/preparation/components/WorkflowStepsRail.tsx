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

/* What the rail turns into below the large breakpoint. A step with a record behind it
   reads as the design's compact header: the open stage's name and its position over a bar
   of one segment per stage. The intake step, which has no record yet, keeps its numbered
   marks - a short stepper under the page's own heading, the way the new-job screen draws
   it. */
type PhoneLayout = "marks" | "segments";

interface WorkflowStepsRailProps {
  label: string;
  phone?: PhoneLayout;
  steps: WorkflowStep[];
}

/* No `overflow-hidden`. It was there to keep the corners clean, but with the row inside it
   set to scroll, what it actually did was cut the flow's last steps off the frame at the
   widths this screen is read at. Nothing here is positioned outside the box, so the corners
   survive without it. */
const railClasses =
  "w-full min-w-0 rounded-control border border-cv-border bg-cv-surface px-3 py-3 shadow-surface sm:px-4 lg:rounded-surface lg:py-1.5 lg:shadow-none";

/* On a phone the rail drops its frame: it is part of the page's header there, not a card
   above it, and a framed band ate a sixth of the screen before the step began. */
const phoneRailClasses = "max-lg:rounded-none max-lg:border-0 max-lg:bg-transparent max-lg:p-0 max-lg:shadow-none";

/* Three shapes, heaviest for what is done: a filled mark with a tick, a ring around the
   number of the step the work is at, a light outline for what is ahead. A completed step
   used to sit in a pale outline hardly different from an upcoming one, so only the tick
   told them apart, while the open step was the one filled solid - the spine read heaviest
   at the step not yet done. */
/* From the large breakpoint the desktop design's thin stepper: the open step's mark is
   filled too, numbered rather than ticked, so the two filled shapes still differ in what
   they carry while the row reads as one quiet band under the page's own header. */
const stepMarkClasses: Record<WorkflowStepState, string> = {
  complete: "border-cv-accent bg-cv-accent text-cv-on-accent",
  current: "border-2 border-cv-accent bg-cv-surface text-cv-accent lg:border lg:bg-cv-accent lg:text-cv-on-accent",
  upcoming: "border-cv-border-strong bg-cv-surface text-cv-text-muted",
};

const stepLabelClasses: Record<WorkflowStepState, string> = {
  complete: "font-semibold text-cv-text",
  current: "font-bold text-cv-accent",
  upcoming: "font-medium text-cv-text-muted",
};

/* The design's connectors are solid hairlines: dark up to the open step, light after it. */
const connectorClasses: Record<WorkflowStepState, string> = {
  complete: "bg-cv-success",
  current: "bg-cv-accent",
  upcoming: "workflow-track-upcoming lg:bg-none! lg:bg-cv-border-strong",
};

const StepMark = ({ index, phone, state }: { index: number; phone: PhoneLayout; state: WorkflowStepState }) => (
  <span
    aria-hidden="true"
    className={cx(
      "relative z-(--cv-z-content-raised) flex size-8 shrink-0 items-center justify-center rounded-pill border",
      "text-support font-bold transition-[background-color,border-color,color] duration-200",
      phone === "segments" ? "max-lg:hidden" : "max-lg:size-6 max-lg:text-caption",
      "lg:size-6 lg:text-caption",
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
const StepBody = ({ index, phone, step }: { index: number; phone: PhoneLayout; step: WorkflowStep }) => (
  <span
    className={cx(
      /* Tightens rather than truncates: below the wide breakpoints the padding and the gap
         between mark and label give up their room first, so the words themselves never
         have to. */
      "relative flex min-w-0 flex-1 items-center gap-2 p-1 text-heading-sm transition-colors duration-200 lg:gap-2.5 lg:px-2 lg:py-1.5 lg:text-support",
      /* Unpositioned on a phone's bar, so the open stage's name below can hang from the
         rail's own corner rather than from its segment. */
      phone === "segments" && "max-lg:static max-lg:w-full max-lg:p-0",
      phone === "marks" && "max-lg:text-support",
      stepLabelClasses[step.state],
      step.state === "current" && "font-bold",
    )}
  >
    <StepMark index={index} phone={phone} state={step.state} />
    {/* The phone's segment: filled up to and including the open stage, the way the
        board's cards draw a CV's progress. */}
    {phone === "segments" ? (
      <span
        aria-hidden="true"
        className={cx("h-1 w-full rounded-pill lg:hidden", step.state === "upcoming" ? "bg-cv-border" : "bg-cv-accent")}
      />
    ) : null}
    {/* Below the large breakpoint the spine is a row of marks across the top of the
        screen, and only the open step keeps its words: four labels abreast do not fit a
        phone, and stacked they pushed the page's own heading below the fold. The marks'
        shapes still carry every step's state, and each link keeps its own name. */}
    {/* On the phone's bar the open stage's name is the header's title: it leaves its
        segment for the rail's top corner, opposite the count, so the name is drawn once
        rather than copied into a header of its own. */}
    <span
      className={cx(
        "min-w-0 flex-1 whitespace-nowrap",
        phone === "segments"
          ? step.state === "current"
            ? "max-lg:absolute max-lg:start-0 max-lg:top-0 max-lg:text-support max-lg:leading-5 max-lg:text-cv-text"
            : "sr-only lg:not-sr-only"
          : step.here !== true && step.state !== "current" && "sr-only lg:not-sr-only",
      )}
    >
      {step.label}
    </span>
    {/* The press cue shows on hover and focus only. Drawn at rest, a `‹` beside every
        reachable step sat against the connector after it, so between two completed steps
        the spine read "line, chevron, line" where everywhere else it read "line". */}
    {step.href === undefined ? null : (
      <ChevronLeft
        aria-hidden="true"
        className="hidden size-icon-md shrink-0 text-cv-text-muted opacity-0 transition-[opacity,transform] lg:block duration-200 group-hover:-translate-x-0.5 group-hover:text-cv-accent group-hover:opacity-100 group-focus-visible:opacity-100"
      />
    )}
  </span>
);

/* The workflow's route-level axis: one row of marks across the top of the step, above
   its heading, at every width. It used to turn into a column beside the content from the
   large breakpoint, which reserved that column for the rail's own height - a hole under
   a short step's heading, and on the draft step a narrower editor for the whole page. */
export const WorkflowStepsRail = ({ label, phone = "segments", steps }: WorkflowStepsRailProps) => {
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
    <div className={cx("flex flex-col gap-2", phone === "segments" && "max-lg:relative max-lg:gap-0")}>
      {/* Decorative: the nav's own `aria-label` already states the label and the
          position in words, so this repeats it for sighted readers only.

          A phone's bar keeps only the count here, at the row's far end; the open stage's
          name takes the near end (see `StepBody`). The new-job stepper has no header at
          all: the page's heading right above it already says what the marks count. */}
      <div
        aria-hidden="true"
        className={cx(
          "flex shrink-0 flex-wrap items-baseline gap-x-2",
          phone === "segments" ? "max-lg:min-h-5" : "max-lg:hidden",
          /* From the large breakpoint the page's own header names the step and the marks
             count it, so the rail is the design's bare stepper. The nav's label still
             says the position in words. */
          "lg:hidden",
        )}
      >
        <span className={cx("text-heading-sm font-bold text-cv-text", phone === "segments" && "max-lg:hidden")}>
          {label}
        </span>
        {/* The count never breaks across lines. Beside a two-line label in the 13rem
            spine column there is room for about half of it, and the wrap fell inside the
            phrase - "הושלם 4" over "מתוך 4" - which reads as two numbers rather than one
            ratio. Held together it drops to its own line instead. */}
        {progressText === null ? null : (
          <span
            className={cx(
              "text-caption whitespace-nowrap text-cv-text-muted",
              phone === "segments" && "max-lg:ms-auto max-lg:leading-5 max-lg:font-semibold",
            )}
          >
            {progressText}
          </span>
        )}
      </div>

      {/* Every step, always drawn. This used to be a bar-less horizontal scroller, on the
          reasoning that the keyboard reaches each step in order anyway - but a sighted
          reader has no way to know a stage exists past the edge of a strip that shows no
          scrollbar, and the spine's whole job is to say where the work stands across all
          four.

          One row of marks joined by connectors that absorb the spare width. Below the
          large breakpoint - a phone, a split window - only the open step keeps its label,
          so all four stay visible in one short band above the heading. */}
      <div className="min-w-0">
        {/* On a phone's bar the segments sit a short gap apart, and a reachable stage's
            44px target spills above and below its 4px segment rather than spacing them. */}
        <div
          className={cx(
            "flex items-center",
            phone === "segments" && "max-lg:gap-1",
            phone === "segments" && (navigable ? "max-lg:-my-2.5" : "max-lg:mt-2"),
          )}
        >
          {steps.map((step, index) => {
            const body = <StepBody index={index} phone={phone} step={step} />;
            /* The open screen's tint marks a chip; a segment is marked by its fill. */
            const segment = phone === "segments" && "max-lg:min-w-0 max-lg:flex-1 max-lg:shrink";
            /* The open screen's tint is the phone's and the narrow window's: on the desktop
               stepper the filled, numbered mark and the bold label already say it. */
            const hereTint =
              step.here === true && "border-cv-accent/25 bg-cv-accent-soft lg:border-transparent lg:bg-transparent";
            const next = steps[index + 1];

            return (
              <Fragment key={step.label}>
                {step.href === undefined ? (
                  <div
                    aria-hidden="true"
                    className={cx(
                      "flex shrink-0 rounded-control border border-transparent",
                      hereTint,
                      segment,
                      segment && "max-lg:border-0 max-lg:bg-transparent",
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
                      "group flex min-h-11 shrink-0 items-center rounded-control border border-transparent",
                      "transition-[background-color,border-color,box-shadow] duration-200",
                      "hover:border-cv-border hover:bg-cv-surface-muted",
                      hereTint,
                      segment,
                      segment && "max-lg:border-0 max-lg:bg-transparent max-lg:hover:bg-transparent",
                    )}
                    to={step.href}
                  >
                    {body}
                  </Link>
                )}

                {next === undefined ? null : (
                  <span
                    aria-hidden="true"
                    className={cx(
                      "h-px min-w-3 flex-1 lg:mx-2",
                      phone === "segments" && "max-lg:hidden",
                      connectorClasses[next.state],
                    )}
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
      <div aria-label={description} className={cx(railClasses, phoneRailClasses)} role="img">
        <div aria-hidden="true">{content}</div>
      </div>
    );
  }

  return (
    <nav aria-label={description} className={cx(railClasses, phoneRailClasses)}>
      {content}
    </nav>
  );
};
