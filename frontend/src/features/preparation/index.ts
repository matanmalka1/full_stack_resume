/* The CV preparation feature's public surface: where one Application's document work
   stands, what it is waiting on, and the vocabulary that names both.

   This is the domain the Application hub composes a tab from, not the hub itself. The
   split matters in one direction: `applications` may reach in here, and nothing here
   reaches back - the labels below are preparation's own words, which is why the board,
   the draft editor and the revision screen read them from here rather than from the
   Application feature they used to sit in.

   A consumer that needs something not listed here needs it added here, not imported from
   inside. */

export { PreparationView } from "./components/PreparationView";
/* The two preparation badges as one row, for a masthead that already lays one out. */
export { PreparationStatusBadges } from "./components/PreparationStatusBadges";
/* Where the work stands across the three stages, for the three screens that are part of
   preparing one CV: the hub, the editor, and the revision. */
export { PreparationWorkflowSteps } from "./components/PreparationWorkflowSteps";

/* The Web automation continuation from a finished analysis to its draft. Called by the
   screen that holds the watch, because that is where the Operation being followed is. */
export { useAutomaticDraft } from "./api/mutations";

/* What the projection is asking the reader to decide, for a caller that counts it into a
   badge. Where those decisions are taken stays inside. */
export { openDecisionCount, openDecisions } from "./model/reviewDecisions";

export { actionDestination } from "./model/actionDestinations";
export { fitLevelIcon, fitLevelLabel, fitLevelTone, trackLabel } from "./model/analysisLabels";
export {
  actionLabel,
  preparationStateIcons,
  preparationStateLabels,
  preparationStateTones,
  reasonTitle,
  warningDetail,
  warningTitle,
  workingDraftStateLabels,
  workingDraftStateTones,
} from "./model/preparationLabels";
/* What the SelectionPlan decided about a fact. The draft editor names the same decisions
   beside the facts it offers to include, so the words are defined once. */
export { omissionReasonLabels, selectionOutcomeLabels } from "./model/selectionLabels";
