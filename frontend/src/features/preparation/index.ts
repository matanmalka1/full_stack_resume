/* The CV preparation feature's public surface: where one Application's document work
   stands, what it is waiting on, and the vocabulary that names both.

   This is the domain the Application hub composes a tab from, not the hub itself. The
   split matters in one direction: `applications` may reach in here, and nothing here
   reaches back - the labels below are preparation's own words, which is why the board,
   the draft editor and the ready screen read them from here rather than from the
   Application feature they used to sit in.

   A consumer that needs something not listed here needs it added here, not imported from
   inside. */

/* The CV-preparation step of the workflow wizard: the verdict, the one action the
   workflow is waiting on, and the facts, diagnosis and posting a press away. The hub
   renders it as the body of the preparation screen. */
export { PreparationView } from "./components/PreparationView";
/* The frame a step of the flow is drawn in: the spine that says where the work stands, the
   heading named from the stage table, and the measure. A screen in the flow renders this
   instead of assembling its own `PageShell` around the same three things - which is what
   kept a step's heading and its chip two independently written answers to one question.
   The spine itself is reached only through here. */
export { WizardStepShell } from "./components/WizardStepShell";
/* What the projection is refusing and why, with the way to the control that answers it.
   The draft editor and the ready screen report the same review reasons and warnings this
   screen does, so it
   renders this region rather than a thinner copy of it that names a blocker without
   naming a way out. */
export { PreparationAlerts } from "./stages/verification/PreparationAlerts";

/* The Web automation continuation from a finished analysis to its draft. Called by the
   screen that holds the watch, because that is where the Operation being followed is. */
export { useAutomaticDraft } from "./api/mutations";

/* What the projection is asking the reader to decide, for a caller that counts it into a
   badge. Where those decisions are taken stays inside. */

export {
  actionDestination,
  preparationResumeDestination,
  preparationResumeDestinationFromDetail,
} from "./model/actionDestinations";
export {
  confidenceText,
  emphasisLabels,
  fitLevelLabel,
  languageLabels,
  profileLabels,
  trackLabel,
} from "./model/analysisLabels";
export {
  actionDescription,
  actionLabel,
  preparationStateIcons,
  preparationStateLabels,
  preparationStateTones,
  reasonTitle,
  warningTitle,
} from "./model/preparationLabels";
/* What the document's selection decided about a fact. The draft editor names the same decisions
   beside the facts it offers to include, so the words are defined once. */
export { omissionReasonLabels } from "./model/selectionLabels";
