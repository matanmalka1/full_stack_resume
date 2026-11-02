/* The CV preparation feature's public surface: where one Application's document work
   stands, what it is waiting on, and the vocabulary that names both.

   This is the domain the Application hub composes a tab from, not the hub itself. The
   split matters in one direction: `applications` may reach in here, and nothing here
   reaches back - the labels below are preparation's own words, which is why the board,
   the draft editor and the ready screen read them from here rather than from the
   Application feature they used to sit in.

   A consumer that needs something not listed here needs it added here, not imported from
   inside. */

/* The four stages' names, for the new-job screen's stepper: the step before an
   Application exists draws the same stages without a record to locate it in. */
export { workflowStageLabels, workflowStages } from "./model/workflowStages";
/* What the projection is refusing and why, with the way to the control that answers it.
   The draft editor and the ready screen report the same review reasons and warnings this
   screen does, so it
   renders this region rather than a thinner copy of it that names a blocker without
   naming a way out. */
export { PreparationAlerts } from "./stages/verification/PreparationAlerts";

/* What the projection is asking the reader to decide, for a caller that counts it into a
   badge. Where those decisions are taken stays inside. */

export {
  preparationResumeDestination,
  preparationResumeDestinationFromDetail,
} from "./model/actionDestinations";
export {
  classificationFieldLabels,
  emphasisLabels,
  fitLevelLabel,
  languageLabels,
  profileLabels,
  trackLabel,
} from "./model/analysisLabels";
export { ReasonCallout, ReasonDetails } from "./components/ReasonCallout";
export {
  actionLabel,
  preparationStateLabels,
  reasonTitle,
  warningTitle,
} from "./model/preparationLabels";
