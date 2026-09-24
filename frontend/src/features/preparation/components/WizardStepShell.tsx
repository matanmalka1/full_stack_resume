import { useState, type ReactNode } from "react";

import type { ApplicationDetail } from "@/api/contracts";
import { PageShell } from "@/ui/PageShell";
import { CommitBarTargetContext } from "@/ui/CommitBar";
import { WideRowTargetContext } from "@/ui/WideRow";
import { type WorkflowStage, workflowStageLabels } from "../model/workflowStages";
import { PreparationWorkflowSteps } from "./PreparationWorkflowSteps";

interface WizardStepShellProps {
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
     the wide frame. Intake, which asks one thing and shows nothing beside it, takes the
     narrower wizard measure. */
  measure?: "wide" | "wizard";
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
  /* Only where the record does not actually meet its stage - an approved revision that is
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
  children,
  description,
  detail,
  eyebrow,
  measure = "wizard",
  queryError,
  stage,
  title,
  wideRow = false,
}: WizardStepShellProps) => {
  const [commitBarTarget, setCommitBarTarget] = useState<HTMLDivElement | null>(null);
  const [wideRowTarget, setWideRowTarget] = useState<HTMLDivElement | null>(null);

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
        description={description}
        eyebrow={eyebrow}
        landmark={<PreparationWorkflowSteps applicationId={applicationId} detail={detail} stage={stage} />}
        measure={measure}
        title={title ?? workflowStageLabels[stage]}
      >
        <div className="flex flex-col gap-6">
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
    <WideRowTargetContext.Provider value={wideRow ? wideRowTarget : undefined}>{body}</WideRowTargetContext.Provider>
  );
};
