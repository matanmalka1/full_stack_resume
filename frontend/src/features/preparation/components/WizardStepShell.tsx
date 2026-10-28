import { useState, type ReactNode } from "react";

import type { ApplicationDetail } from "@/api/contracts";
import { boardPath, boardReturnState } from "@/navigation/boardReturn";
import { cx } from "@/ui/cx";
import { PageShell } from "@/ui/PageShell";
import { CommitBarTargetContext } from "@/ui/CommitBar";
import { StatusSlotTargetContext } from "@/ui/StatusSlot";
import { WideRowTargetContext } from "@/ui/WideRow";
import { type WorkflowStage, workflowStageLabels } from "../model/workflowStages";
import { type PhoneHeader, PreparationWorkflowSteps } from "./PreparationWorkflowSteps";

/* What a step changes about its header from the large breakpoint. The desktop design gives
   every step a page header - a way back, the title, who the CV is for under it, and the
   step's commands at the row's end - with the stepper under it rather than a framed rail
   above. Every part is optional: a step that passes nothing gets the bordered back
   chevron, the stage's name, "role · company" and the stepper. */
interface DesktopHeader {
  /* The step's commands at the masthead row's end. Rendered as given AT EVERY WIDTH, so a
     command that has another home on a phone takes `max-lg:hidden` from its caller - and a
     command must never also render somewhere else, or its name is on the page twice. */
  actions?: ReactNode;
  /* The trail "לוח המועמדויות / [title]" above the heading instead of the back chevron. */
  breadcrumb?: boolean;
  /* The company's initial in a tile before the title. */
  mark?: boolean;
  /* Whether the stepper is drawn under the header. Default true; false hides it from the
     large breakpoint only - a phone's header keeps whatever `phoneHeader.bar` says. */
  spine?: boolean;
  /* The muted line under the title. Defaults to "role · company" once the record is read. */
  subtitle?: ReactNode;
  /* The h1's content in place of the stage's name. A phone keeps the h1 for assistive tech
     only on a compact header, so there it becomes the heading's accessible name too. */
  title?: ReactNode;
}

const NO_DESKTOP_HEADER: DesktopHeader = {};

interface WizardStepShellProps {
  /* Classes added to the body's column - the step's own `children` - so a step can lay
     them out as a grid from the large breakpoint without wrapping each one. */
  bodyClassName?: string;
  desktopHeader?: DesktopHeader;
  /* Absent on intake, where the Application does not exist yet, and while the record
     naming it has not loaded. */
  applicationId?: string;
  children?: ReactNode;
  description?: ReactNode;
  /* The projection the spine reads the work's position from. Absent while in flight, and
     absent on intake, where there is nothing to read yet. */
  detail?: ApplicationDetail;
  /* A failed page query owns the whole route surface through QueryState (including its
     404 frame). In that state there is no workflow position to announce, so the wizard
     frame must not draw a heading or progress rail around it. */
  queryError?: unknown;
  /* Who the CV is for. Supplied by the page rather than derived here: the words that name
     an Application belong to the Application feature, and preparation is reached into
     rather than reaching back. */
  eyebrow?: ReactNode;
  /* The analysis, draft and ready steps each put the work beside the evidence for it - the
     facts checklist beside the diagnosis, the draft beside its rendered document, the
     approved record beside its validation - and that split of two readable columns needs
     the wide frame.

     Every step takes it, intake included. Intake used to take the narrower wizard
     measure, and pressing "יצירת מועמדות" then widened the spine, the heading and the
     body in the same paint that swapped the step - the one moment the flow should feel
     like moving forward read as the page being thrown somewhere else. One measure keeps
     the frame still while its contents change. */
  measure?: "wide";
  /* Whether this step gives its body a `WideRow` target - see that component's doc.
     Only the analysis step sets this: its work/reasoning split reads there instead of
     inset beside the rail, so it can use the width the rail's reserved column would
     otherwise leave unused for the rest of the step's height. */
  wideRow?: boolean;
  /* Which step of the flow this screen is, and what the spine marks as current. The
     projection still marks which *other* steps read as already complete - a step ahead of
     this one, reached by revisiting an earlier screen - but it never moves the current
     chip: an in-flight edit can make the projection dip to an earlier state than the
     screen the reader is looking at, and the chip must not chase that back and forth. */
  stage: WorkflowStage;
  /* What the step adds to its compact phone header - a trailing action, a different title
     or subtitle, the company's initial, or no stage bar. See `PhoneHeader`. */
  phoneHeader?: PhoneHeader;
  /* Whether the page's own heading stays in view on a phone. "compact" (the default on
     every step after intake) leaves the header above to name the step, and keeps the
     heading for assistive tech and route focus only; "full" keeps the heading and its
     description visible under the header, as the Ready screen's design does. */
  phoneHeading?: "compact" | "full";
  /* Only where the record does not actually meet its stage - an approved document that is
     not deliverable is not "מוכן למסירה", and saying so in the heading is a distinction
     worth keeping. Everything else takes the stage's own name. */
  title?: ReactNode;
}

/* The frame every step of the CV wizard is drawn in: the spine, the heading, and the
   measure, in one place.

   Each of the four steps used to assemble this itself, and the copies drifted the way
   hand-kept copies do - the heading naming the step differently from the chip above it on
   two of the four screens, repaired once for the draft step and left standing on the other
   two. A step now says which stage it is and gets its name from the same table the spine
   marks it with, so that agreement holds by construction rather than by review. */
export const WizardStepShell = ({
  applicationId,
  bodyClassName,
  children,
  description,
  desktopHeader = NO_DESKTOP_HEADER,
  detail,
  eyebrow,
  measure = "wide",
  phoneHeader,
  phoneHeading = "compact",
  queryError,
  stage,
  title,
  wideRow = false,
}: WizardStepShellProps) => {
  const [commitBarTarget, setCommitBarTarget] = useState<HTMLDivElement | null>(null);
  const [wideRowTarget, setWideRowTarget] = useState<HTMLDivElement | null>(null);
  const [statusTarget, setStatusTarget] = useState<HTMLDivElement | null>(null);

  const intake = stage === "intake";
  const company = detail?.application.company;
  const role = detail?.application.target_role;
  const initial = company?.trim().charAt(0);

  /* The desktop header's sub-line: who the CV is for. The phone's header already says it,
     so it is drawn from the large breakpoint only, where the eyebrow saying the same thing
     above the title gives way to it. */
  const subtitle =
    desktopHeader.subtitle ??
    (role === undefined || company === undefined ? undefined : <span dir="auto">{`${role} · ${company}`}</span>);
  const pageDescription =
    subtitle === undefined ? (
      description
    ) : (
      <>
        <span className="block max-lg:hidden">{subtitle}</span>
        {description === undefined ? null : <span className="block lg:mt-2">{description}</span>}
      </>
    );
  /* The phone's heading: the step's own title, or the stage's name - in view only where
     the phone header does not already name it. */
  const phoneTitle =
    title ??
    (intake || phoneHeading === "full" ? (
      workflowStageLabels[stage]
    ) : (
      <span className="max-lg:sr-only">{workflowStageLabels[stage]}</span>
    ));
  /* A desktop title replaces it from the large breakpoint only, so a phone keeps the
     heading it had; each half is display:none at the other's width. */
  const pageTitle =
    desktopHeader.title === undefined ? (
      phoneTitle
    ) : (
      <>
        <span className="lg:hidden">{phoneTitle}</span>
        <span className="max-lg:hidden">{desktopHeader.title}</span>
      </>
    );
  const stageTitle = desktopHeader.title ?? title;
  /* The way back. A phone draws it in its compact header (the spine's own link); from the
     large breakpoint it is the header's bordered chevron, or the first step of the trail.
     Named apart from the phone's link, which is display:none here and the only one there,
     so the page never holds two links of one name. */
  const boardLink = { state: boardReturnState(applicationId), to: boardPath() };

  if (queryError !== null && queryError !== undefined) {
    return children;
  }

  const body = (
    <CommitBarTargetContext.Provider value={commitBarTarget}>
      <PageShell
        afterBody={
          wideRow ? (
            /* The commit bar's target moves in here too, and after the wide row's own
               target rather than staying at the end of the inset `children` flow below:
               `position: sticky` only has room to visibly float within its own
               containing block, and once the wide row's content moved out of that inset
               flow, that flow was left too short to hold it - the bar would sit
               statically instead of pinning to the viewport bottom, unlike every other
               step. Placed after the wide row's target so it still closes the step, the
               same order `WorkflowActions`' own doc describes. */
            <div className="flex flex-col gap-6">
              <div className="contents" ref={setWideRowTarget} />
              <div className="contents" ref={setCommitBarTarget} />
            </div>
          ) : undefined
        }
        actions={desktopHeader.actions}
        back={desktopHeader.breadcrumb === true ? undefined : { label: "חזרה ללוח", ...boardLink }}
        breadcrumb={
          desktopHeader.breadcrumb === true
            ? [{ label: "לוח המועמדויות", ...boardLink }, { label: stageTitle ?? workflowStageLabels[stage] }]
            : undefined
        }
        description={pageDescription}
        /* The phone header names who the CV is for, so the eyebrow saying it again stays
           for assistive tech only there; from the large breakpoint the sub-line under the
           title says it instead. */
        eyebrow={
          eyebrow === undefined || intake ? (
            eyebrow
          ) : (
            <span className={cx("max-lg:sr-only", subtitle !== undefined && "lg:hidden")}>{eyebrow}</span>
          )
        }
        landmark={
          <PreparationWorkflowSteps
            applicationId={applicationId}
            desktopSpine={desktopHeader.spine !== false}
            detail={detail}
            phoneHeader={phoneHeader}
            stage={stage}
          />
        }
        landmarkPlacement="below-masthead"
        leading={
          desktopHeader.mark === true && initial !== undefined && initial !== "" ? (
            <span
              className="flex size-12 items-center justify-center rounded-surface border border-cv-border bg-cv-surface text-heading-sm font-extrabold text-cv-text"
              dir="auto"
            >
              {initial}
            </span>
          ) : undefined
        }
        measure={measure}
        title={
          /* On a compact phone header the stage bar above already names the step, so the
             heading stays for assistive tech and route focus only. A page's own title - a
             stage its record does not actually meet - says something the bar does not,
             and stays in view. */
          pageTitle
        }
      >
        <div className={cx("flex flex-col gap-6", bodyClassName)}>
          {/* The step's Operation status, first on every step - see `StatusSlot`. */}
          <div className="contents" ref={setStatusTarget} />
          {children}
          {wideRow ? null : <div className="contents" ref={setCommitBarTarget} />}
        </div>
      </PageShell>
    </CommitBarTargetContext.Provider>
  );

  /* Always the same tree, so a step that turns its wide row on or off - the analysis
     step, once an analysis arrives - does not remount its body (and the Operation
     overlay inside it) at that moment. `undefined` makes `WideRow` render in place. */
  return (
    <StatusSlotTargetContext.Provider value={statusTarget}>
      <WideRowTargetContext.Provider value={wideRow ? wideRowTarget : undefined}>{body}</WideRowTargetContext.Provider>
    </StatusSlotTargetContext.Provider>
  );
};
