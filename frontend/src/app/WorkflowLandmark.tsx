import { createContext, type ReactNode, useContext, useLayoutEffect, useMemo, useState } from "react";

import type { ApplicationDetail, PreparationState } from "../api/contracts";
import { useLocation } from "react-router-dom";

import { type WorkflowStep, WorkflowSteps } from "../ui/WorkflowSteps";

/* A.4 frame 1 region 3: five ordered stages, and the only place their Hebrew names
   live. */
const stages = ["intake", "analysis", "draft", "validation", "ready"] as const;

type Stage = (typeof stages)[number];

const stageLabels: Record<Stage, string> = {
  intake: "משרה חדשה",
  analysis: "ניתוח",
  draft: "טיוטה",
  validation: "אימות",
  ready: "מוכן",
};

/* What each stage produces, in one line. The labels above are single nouns, and a noun
   alone does not tell a reader what "אימות" is for or what has to be true before "מוכן".
   Only the current stage's line is shown, so the landmark stays one sentence tall.

   These describe the stage, not what may happen next: which action is possible is
   `available_actions` and `recommended_action`, and the landmark still decides none of
   it (A.1). */
const stageHints: Record<Stage, string> = {
  intake: "קליטת המודעה ויצירת המשרה",
  analysis: "התאמת המשרה לעובדות הקנוניות",
  draft: "ניסוח קורות החיים לפי תוכנית הבחירה",
  validation: "בדיקת הניסוח מול העובדות לפני אישור",
  ready: "גרסה מאושרת ומרונדרת, מוכנה לשליחה",
};

/* The stage the hint describes: where the work is, and at `ready` the stage it finished
   on. `unknown` gets none - the stage it is on is not this module's to guess. */
const hintFor = (stage: Exclude<WorkflowStage, "none">): string | undefined =>
  stage === "unknown" ? undefined : stageHints[stage === "intake" ? "intake" : stageForPreparationState[stage]];

/* Where the backend's PreparationState sits in the landmark. Exhaustive over the
   generated union, so a state added to the projection fails the build here rather than
   leaving the landmark on whichever stage it happened to be showing.

   This is a display position, not a second workflow state machine (A.1). It decides
   nothing about what may happen next: that comes from `available_actions` and
   `recommended_action`. A stage the projection has already reached is navigable, because
   its screen exists and holds what it produced. A future stage is not: reaching it is an
   action the projection allows, not a place. */
const stageForPreparationState: Record<PreparationState, Stage> = {
  needs_analysis: "analysis",
  needs_review: "analysis",
  ready_to_draft: "draft",
  draft_in_progress: "draft",
  ready_for_approval: "validation",
  approved: "ready",
  ready: "ready",
};

/* Whether the landmark's stage already says everything the preparation badge would.

   Derived from the map above rather than listed: a state sharing its stage with another
   is the one the badge distinguishes ("ניתוח" is both `needs_analysis` and `needs_review`),
   and a state that is alone on its stage is that stage under a second name. Adding a
   preparation state re-answers this on its own; it cannot be forgotten here. */
export const preparationStateIsImpliedByStage = (state: PreparationState): boolean => {
  const stage = stageForPreparationState[state];
  return Object.values(stageForPreparationState).filter((entry) => entry === stage).length === 1;
};

export type StageDestinations = Partial<Record<Stage, string>>;

/* Where each stage's work can be re-read, derived from the projection rather than listed
   by hand. A stage whose record does not exist yet gets no entry, so the landmark offers
   a link only where there is something at the other end.

   Draft and validation share the editor: validation is a panel of the screen holding the
   draft it validates, not a screen of its own (router.tsx). Ready names the revision the
   Application currently stands on - `latest_ready_revision_id` first, because a rendered
   revision is the one the reader means by "מוכן", and the approved revision only while no
   render exists yet. */
export const workflowDestinations = (
  applicationId: string,
  detail: ApplicationDetail | undefined,
): StageDestinations => {
  const application = `/applications/${encodeURIComponent(applicationId)}`;
  const readyRevisionId = detail?.latest_ready_revision_id ?? detail?.latest_approved_revision_id ?? null;
  const editable = detail?.active_working_draft_id != null;

  return {
    /* Intake produced the job record, and Job Detail is the screen that holds it. */
    intake: application,
    analysis: `${application}/preparation`,
    ...(editable ? { draft: `${application}/draft`, validation: `${application}/draft` } : {}),
    ...(readyRevisionId == null ? {} : { ready: `/revisions/${encodeURIComponent(readyRevisionId)}` }),
  };
};

/* Three kinds of screen, not two.

   `intake` is the screen that exists before an Application does. `unknown` is an
   Application whose projection has not arrived yet, which is a different thing: its
   intake is behind it, but the stage it is on is not this module's to guess.

   `none` is a screen standing outside the workflow altogether - Settings, a not-found
   route - where no stage is the honest answer and the landmark has nothing to report. */
export type WorkflowStage = PreparationState | "intake" | "none" | "unknown";

/* `none` never reaches here: the landmark renders no steps at all for it, rather than a
   row of five in which every one is `upcoming`. Every other stage keeps its exact
   behavior. */
const workflowStepsFor = (stage: Exclude<WorkflowStage, "none">, destinations: StageDestinations): WorkflowStep[] => {
  const current = stage === "intake" ? 0 : stage === "unknown" ? -1 : stages.indexOf(stageForPreparationState[stage]);
  /* `ready` completes its own stage: everything is done, so nothing is in progress.
     `unknown` completes only the intake it is certainly past. */
  const completed = stage === "unknown" ? 1 : stage === "ready" ? current + 1 : current;

  return stages.map((stage_, index) => {
    const state = index < completed ? "complete" : index === current ? "current" : "upcoming";

    return {
      label: stageLabels[stage_],
      state,
      /* Never forward. The current stage is included because "current" is a position in
         the projection, not a claim about which screen is open: at `ready_for_approval`
         read from the preparation screen, אימות is the current stage and its screen is
         the editor, one the reader is not on. The one case the rule must exclude - the
         stage whose screen is the one being read - is excluded where that is known, in
         `WorkflowLandmarkSteps`. A future stage has no record to open. */
      ...(state !== "upcoming" && destinations[stage_] !== undefined ? { href: destinations[stage_] } : {}),
    };
  });
};

interface WorkflowPosition {
  destinations: StageDestinations;
  stage: WorkflowStage;
}

const WorkflowStageContext = createContext<((position: WorkflowPosition) => void) | undefined>(undefined);
/* `none` before any screen has spoken, not `intake`. The claim belongs to the page, and
   until one makes it the honest answer is that no stage is known - a default of `intake`
   made the shell assert stage 1 of 5 on whatever screen loaded first, including the
   Application list. */
const WorkflowStageValueContext = createContext<WorkflowPosition>({ destinations: {}, stage: "none" });

/* The landmark is a shell region (A.1) but the projection belongs to the page, so the
   page states the stage rather than the shell inferring it from the URL.

   Publishing is mandatory, because the claim is no longer reset on unmount: a route that
   says nothing inherits whatever the previous screen left behind. Each of the three kinds
   says its own - an Application route its `PreparationState`, the intake screen `intake`,
   and a screen outside the workflow `none`. */
export const WorkflowLandmark = ({ children }: { children: ReactNode }) => {
  const [position, setPosition] = useState<WorkflowPosition>({ destinations: {}, stage: "none" });

  return (
    <WorkflowStageValueContext.Provider value={position}>
      <WorkflowStageContext.Provider value={setPosition}>{children}</WorkflowStageContext.Provider>
    </WorkflowStageValueContext.Provider>
  );
};

/* Split from the provider so the shell can place the steps above the page surface while
   the stage itself still comes from the page rendered below it. */
export const WorkflowLandmarkSteps = () => {
  const { destinations, stage } = useContext(WorkflowStageValueContext);
  const { pathname } = useLocation();

  /* Off-workflow screens get no landmark rather than a stale one. Without this, removing
     the unmount reset would leave Settings showing whichever stage the previous screen
     published - the breadcrumb still claiming "אימות" while the user is in Settings. */
  if (stage === "none") {
    return null;
  }

  const steps = workflowStepsFor(stage, destinations);
  /* Which of the five stages the open screen belongs to. The shell's knowledge, not the
     page's: the pages derive destinations from the projection alone, and matching a
     destination against the open path is what turns that into a location.

     The current stage wins a tie, because the editor is the screen of both טיוטה and
     אימות and the projection is what says which of the two the reader is doing there.
     `intake` is matched by the stage rather than by a path: the intake screen exists
     before the Application does, so it has no destination to compare against. */
  const hereIndex =
    stage === "intake"
      ? 0
      : steps.findIndex((step) => step.state === "current" && step.href === pathname) !== -1
        ? steps.findIndex((step) => step.state === "current" && step.href === pathname)
        : steps.findIndex((step) => step.href === pathname);

  /* A stage whose screen is the one being read is not a way back. Dropped here for the
     same reason the location is decided here. */
  const located = steps.map((step, index) => ({
    ...(index === hereIndex ? { here: true } : {}),
    ...(step.href === pathname ? {} : { href: step.href }),
    label: step.label,
    state: step.state,
  }));

  return (
    <WorkflowSteps
      /* The line describes the screen the reader is on where that is one of the five, and
         falls back to the stage the work is on where it is not - a revision opened from
         outside the workflow, say. */
      hint={hereIndex === -1 ? hintFor(stage) : stageHints[stages[hereIndex]]}
      label="שלבי הכנת קורות החיים"
      steps={located}
    />
  );
};

export const useWorkflowStage = (stage: WorkflowStage, destinations?: StageDestinations): void => {
  const publish = useContext(WorkflowStageContext);
  /* The caller derives the destinations on every render, so the object identity changes
     each time while its content usually does not. Keying the effect on the content keeps
     a screen from republishing its position on every render. */
  const key = JSON.stringify(destinations ?? {});
  const published = useMemo(() => JSON.parse(key) as StageDestinations, [key]);

  /* Layout, not effect: the landmark renders above the page that publishes to it, so a
     passive effect let the browser paint one frame of the previous screen's stage on the
     new one - the five steps flashing over the Application list on the way back to it.
     Committing the claim before paint removes that frame. */
  useLayoutEffect(() => {
    publish?.({ destinations: published, stage });
    /* No reset on unmount. Resetting here produced a flash of `intake` between two
       screens that were both mid-workflow - the landmark appearing to restart while the
       user moved from the editor to the operation it queued.

       That makes publishing mandatory rather than optional: a screen that publishes
       nothing now inherits the stage the previous one left behind. Every route states
       its own answer, including `intake` and `none`. */
  }, [publish, published, stage]);
};
