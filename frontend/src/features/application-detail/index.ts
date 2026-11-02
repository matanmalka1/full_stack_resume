/* The Applications feature's public surface: one Application as a record - which job it
   is, where it stands on both axes, and the way into the domains that do the work.

   It composes preparation, recruitment and its own artifact inventory; it owns none of
   their logic. What it does own is the Application's identity, so the label and the
   posting's source line are exported for the screens that name the same record from
   outside. Its screens are not exported: the route table loads each one on its own. */
export { applicationLabel, sourceHostname } from "./model/applicationPresentation";
/* The record's quick look and its two endings, which the board asks about its cards
   exactly as the hub asks about its own record. */
export { type ApplicationDetailsSummary, ApplicationDetailsSheet } from "./components/ApplicationDetailsSheet";
export { CloseApplicationDialog } from "./components/CloseApplicationDialog";
export { DeleteApplicationDialog } from "./components/DeleteApplicationDialog";
export {
  isJobTextWithinBudget,
  JOB_TEXT_REQUIRED_MESSAGE,
  jobTextByteLength,
  LABEL_MAX_CHARACTERS,
  normalizedSourceUrl,
  SOURCE_URL_MAX_CHARACTERS,
  validateSourceUrl,
} from "./model/applicationInput";
