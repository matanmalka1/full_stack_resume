import { useState, type ReactNode } from "react";

import type { ApplicationDetail } from "@/api/contracts";
import { PageShell } from "@/ui/PageShell";
import { type WorkflowStage, workflowStageLabels } from "../model/workflowStages";
import { PreparationWorkflowSteps } from "./PreparationWorkflowSteps";
import { CommitBarTargetContext } from "./CommitBar";

interface WizardStepShellProps {
  /* Absent on intake, where the Application does not exist yet, and while the record
     naming it has not loaded. */
  applicationId?: string;
  children?: ReactNode;
  description?: ReactNode;
  /* The projection the spine reads the work's position from. Absent while in flight, and
     absent on intake, where there is nothing to read yet. */
  detail?: ApplicationDetail;
  /* Who the CV is for. Supplied by the page rather than derived here: the words that name
     an Application belong to the Application feature, and preparation is reached into
     rather than reaching back. */
  eyebrow?: ReactNode;
  /* The draft editor is the one step whose content is a document beside the evidence for
     each of its lines, and that split of two readable columns needs the wide frame. Every
     other step asks one thing and takes the narrower wizard measure. */
  measure?: "wide" | "wizard";
  /* Which step of the flow this screen *is* - not where the work stands, which the spine
     reads from the projection. The two differ on purpose: the analysis screen is still the
     analysis step when it is opened against a draft awaiting approval. */
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
  stage,
  title,
}: WizardStepShellProps) => {
  const [commitBarTarget, setCommitBarTarget] = useState<HTMLDivElement | null>(null);

  return (
    <CommitBarTargetContext.Provider value={commitBarTarget}>
      <PageShell
        description={description}
        eyebrow={eyebrow}
        /* The spine states the position it reads from the projection. Only a screen with no
           Application to read it from - intake - names its own, which is exactly the case
           where there is no id either. */
        landmark={
          <PreparationWorkflowSteps
            applicationId={applicationId}
            detail={detail}
            stage={applicationId === undefined ? stage : undefined}
          />
        }
        measure={measure}
        title={title ?? workflowStageLabels[stage]}
      >
        <div className="flex flex-col gap-6">
          {children}
          <div className="contents" ref={setCommitBarTarget} />
        </div>
      </PageShell>
    </CommitBarTargetContext.Provider>
  );
};
